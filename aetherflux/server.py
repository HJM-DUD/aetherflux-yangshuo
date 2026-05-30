"""Local dashboard and internal JSON API server."""

from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict
from urllib.parse import parse_qs, urlparse

from .api import build_public_payloads
from .deepseek import DeepSeekAdvisorError, DeepSeekClient, DeepSeekConfig, read_deepseek_status
from .pipeline import run_ingest, run_review
from .storage import IntelligenceStore

WEB_DIR = Path(__file__).parent / "web"
DEFAULT_DIRECTIONS = Path("config/directions.json")
from .paths import seed_items_path
DEFAULT_SEED = seed_items_path()
DEFAULT_DASHBOARD_PORT = 8788
DEFAULT_WORKER_API_PORT = 8789


def render_index() -> str:
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")


def build_system_status(store: IntelligenceStore) -> Dict[str, Any]:
    config = DeepSeekConfig.from_env()
    advisor_connection = build_advisor_connection(config)
    directions = _load_directions()
    platforms = directions.get("platform_weights", {})
    candidates = store.list_candidates(limit=500)
    return {
        "project": {
            "name_zh": "以太通量",
            "name_en": "AetherFlux",
            "subproject": "阳朔旅游情报决策系统",
            "mode": "Codex-controlled daily intelligence center",
        },
        "deepseek": {
            "enabled": config.enabled,
            "base_url": config.base_url,
            "model": config.model,
            "key_source": "DEEPSEEK_API_KEY" if config.enabled else "not_configured",
            "connection": advisor_connection,
        },
        "first_platform": {
            "id": "xiaohongshu",
            "label": "小红书首采",
            "status": "collector_ready",
            "next_step": "接入登录态浏览器或 opencli 驱动，持续输出 raw item schema。",
        },
        "ports": {
            "web": DEFAULT_DASHBOARD_PORT,
            "worker_api": DEFAULT_WORKER_API_PORT,
            "reserved_triagent": 8765,
        },
        "storage": {
            "mode": "local_sqlite",
            "evidence_retention_hours": store.get_retention_hours(),
            "cloud_log_months": store.get_cloud_log_months(),
            "cloud_scope": "login_and_daily_log_index_only",
        },
        "collector": {
            "mode": "local_first_video_collector",
            "platforms": ["xiaohongshu", "douyin", "wechat_channels"],
            "dedupe_policy": "hard_dedupe_only_for_exact_duplicates_topic_cluster_keeps_multi_user_signals",
        },
        "modules": {
            "collector": {"status": "xhs_collector_ready", "description": "小红书已支持首采、日更、水位线状态和 raw item 输出。"},
            "normalization": {"status": "ready", "description": "统一 raw item schema、语言、时间、来源证据。"},
            "scoring": {"status": "ready", "description": "低 token 规则评分、去重、基础分类。"},
            "cross_verification": {"status": "ready_for_expansion", "description": "交叉验证中心：claim、支持来源、冲突来源、补证建议。"},
            "geo_risk": {"status": "ready_for_expansion", "description": "GEO 疑似度：信息污染、标准答案塑造、叙事操控风险概率。"},
            "bilingual_display": {"status": "ready", "description": "人工审阅和最终呈现阶段中英对照。"},
        },
        "counts": {
            "candidates": len(candidates),
            "directions_platforms": len(platforms),
            "themes": len(directions.get("themes", [])),
            "places": len(directions.get("places", [])),
        },
        "platforms": sorted(platforms.keys()),
    }


def run_server(store: IntelligenceStore, host: str = "127.0.0.1", port: int = DEFAULT_DASHBOARD_PORT) -> None:
    handler = make_handler(store)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"AetherFlux dashboard: http://{host}:{port}")
    httpd.serve_forever()


def make_handler(store: IntelligenceStore) -> type[BaseHTTPRequestHandler]:
    class AetherFluxHandler(BaseHTTPRequestHandler):
        server_version = "AetherFlux/0.1"

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_text(render_index(), "text/html; charset=utf-8")
                return
            if parsed.path.startswith("/static/"):
                self._send_static(parsed.path)
                return
            if parsed.path.startswith("/api/"):
                self._send_json(self._api_get(parsed.path))
                return
            self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            body = self._read_json_body()
            if parsed.path == "/api/decisions":
                candidate_id = str(body.get("id", ""))
                if not candidate_id:
                    self._send_json({"error": "id_required"}, HTTPStatus.BAD_REQUEST)
                    return
                weight = body.get("weight_override")
                weight_override = int(weight) if weight not in (None, "") else None
                store.set_human_decision(
                    candidate_id,
                    str(body.get("status", "pending")),
                    weight_override=weight_override,
                    note=str(body.get("note", "")),
                )
                self._send_json({"ok": True, "candidate": store.get_candidate(candidate_id)})
                return
            if parsed.path == "/api/run-ingest":
                query = parse_qs(parsed.query)
                directions = query.get("directions", [str(DEFAULT_DIRECTIONS)])[0]
                seed = query.get("seed", [str(DEFAULT_SEED)])[0]
                self._send_json(run_ingest(store, directions, seed))
                return
            if parsed.path == "/api/run-review":
                try:
                    self._send_json(run_review(store, str(body.get("webhook_url", "")), top_n=int(body.get("top_n", 20))))
                except DeepSeekAdvisorError as exc:
                    self._send_json({"ok": False, "error": "deepseek_failed", "message": str(exc)}, HTTPStatus.BAD_GATEWAY)
                return
            if parsed.path == "/api/deepseek-smoke-test":
                self._send_json(run_deepseek_smoke_test())
                return
            if parsed.path == "/api/admin/missions":
                store.upsert_mission(
                    str(body.get("id", "")),
                    str(body.get("place", "")),
                    str(body.get("industry", "")),
                    body.get("segments", []),
                )
                self._send_json({"ok": True})
                return
            if parsed.path == "/api/admin/official-sources":
                store.upsert_official_source(
                    str(body.get("id", "")),
                    str(body.get("mission_id", "")),
                    str(body.get("url", "")),
                    str(body.get("label", "")),
                    status=str(body.get("status", "active")),
                    recommended_by=str(body.get("recommended_by", "manual")),
                )
                self._send_json({"ok": True, "items": store.list_official_sources(str(body.get("mission_id", "")))})
                return
            if parsed.path == "/api/admin/retention":
                store.set_retention_hours(
                    int(body.get("evidence_hours", 48)),
                    cloud_log_months=int(body.get("cloud_log_months", store.get_cloud_log_months())),
                )
                self._send_json(
                    {
                        "ok": True,
                        "evidence_hours": store.get_retention_hours(),
                        "cloud_log_months": store.get_cloud_log_months(),
                    }
                )
                return
            self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

        def log_message(self, fmt: str, *args: Any) -> None:
            print("%s - %s" % (self.address_string(), fmt % args))

        def _api_get(self, path: str) -> Dict[str, Any]:
            payloads = build_public_payloads(store)
            if path == "/api/candidates":
                return {"items": store.list_candidates(limit=300)}
            if path == "/api/system-status":
                return build_system_status(store)
            if path == "/api/admin/official-sources":
                return {"items": store.list_official_sources()}
            if path == "/api/admin/retention":
                return {
                    "evidence_hours": store.get_retention_hours(),
                    "cloud_log_months": store.get_cloud_log_months(),
                }
            if path == "/api/daily-bundles":
                return {"items": store.list_daily_bundles()}
            if path == "/api/cloud-log-syncs":
                return {"items": store.list_cloud_log_syncs()}
            if path == "/api/selected":
                return {"items": payloads["selected"]}
            if path == "/api/daily":
                return payloads["daily"]
            if path == "/api/opportunities":
                return {"items": payloads["opportunities"]}
            if path == "/api/foreign-signals":
                return {"items": payloads["foreign_signals"]}
            if path == "/api/risks":
                return {"items": payloads["risks"]}
            if path == "/api/content-briefs":
                return {"items": payloads["content_briefs"]}
            if path == "/api/review-drafts/latest":
                return store.latest_review_draft()
            if path.startswith("/api/evidence/"):
                candidate_id = path.rsplit("/", 1)[-1]
                candidate = store.get_candidate(candidate_id)
                return {"id": candidate_id, "evidence": candidate.get("evidence", []), "candidate": candidate}
            return {"error": "not_found"}

        def _send_static(self, path: str) -> None:
            relative = path.replace("/static/", "", 1)
            target = (WEB_DIR / relative).resolve()
            if not str(target).startswith(str(WEB_DIR.resolve())) or not target.exists():
                self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(target.read_bytes())

        def _read_json_body(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, text: str, content_type: str) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(text.encode("utf-8"))

    return AetherFluxHandler


def _load_directions() -> Dict[str, Any]:
    if not DEFAULT_DIRECTIONS.exists():
        return {}
    return json.loads(DEFAULT_DIRECTIONS.read_text(encoding="utf-8"))


def build_advisor_connection(config: DeepSeekConfig) -> Dict[str, Any]:
    if not config.enabled:
        return {
            "state": "not_configured",
            "indicator": "red",
            "label": "未配置 key",
            "message": "DeepSeek API key 未配置。",
        }
    runtime = read_deepseek_status()
    state = runtime.get("state")
    runtime_model = runtime.get("model")
    if runtime_model and runtime_model != config.model:
        return {
            "state": "model_changed",
            "indicator": "yellow",
            "label": "等待模型回复",
            "message": "模型配置已变更，等待当前模型完成一次真实回复。",
            "last_checked_at": runtime.get("checked_at"),
        }
    if state == "connected":
        return {
            "state": "connected",
            "indicator": "green",
            "label": "已打通",
            "message": "DeepSeek 已返回结构化回复。",
            "last_checked_at": runtime.get("checked_at"),
            "last_replied_at": runtime.get("replied_at"),
        }
    if state == "error":
        return {
            "state": "error",
            "indicator": "red",
            "label": "接入失败",
            "message": runtime.get("error", "DeepSeek 请求失败。"),
            "last_checked_at": runtime.get("checked_at"),
        }
    return {
        "state": "awaiting_reply" if state == "awaiting_reply" else "configured_unverified",
        "indicator": "yellow",
        "label": "等待模型回复",
        "message": "已读取 key，等待 DeepSeek 当前模型完成一次真实回复。",
        "last_checked_at": runtime.get("checked_at"),
    }


def run_deepseek_smoke_test() -> Dict[str, Any]:
    config = DeepSeekConfig.from_env()
    if not config.enabled:
        return {"ok": False, "error": "DEEPSEEK_API_KEY is not configured", "connection": build_advisor_connection(config)}
    result = DeepSeekClient(config).request_json(
        'Return exactly this JSON object: {"ok": true, "module": "deepseek_advisor_smoke_test"}'
    )
    return {
        "ok": bool(result.get("ok")) and not result.get("error"),
        "module": result.get("module"),
        "error": result.get("error"),
        "connection": build_advisor_connection(config),
    }
