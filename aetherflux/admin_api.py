"""FastAPI backend for the V0.2.7 local admin console."""

from __future__ import annotations

import json
import hashlib
import re
import os
import platform as platform_module
import signal
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .api import build_public_payloads
from .server import build_system_status, run_deepseek_smoke_test
from .paths import (
    agentcli_bundle_root,
    daily_bundles_inbox_dir,
    shellcli_bundle_root,
)
from .storage import IntelligenceStore

APP_VERSION = "0.2.7"
APP_VERSION_LABEL = "V0.2.7"
JOB_LOG_TAIL_BYTES = 200 * 1024
JOB_TIMEOUT_SECONDS = 7200
JOB_TERMINATE_GRACE_SECONDS = 30

DEFAULT_COLLECT_CONFIG = {
    "platforms": ["xiaohongshu", "douyin"],
    "manual_queries": ["阳朔 旅游", "阳朔 竹筏", "阳朔 西街"],
    "segments": ["景区", "民宿", "酒店", "旅游餐饮", "旅拍", "骑行", "亲子", "研学", "疗愈"],
    "risk_terms": ["避雷", "排队", "投诉", "宰客", "堵车", "价格"],
    "opportunity_terms": ["攻略", "路线", "新玩法", "小众", "体验", "vlog"],
    "hermes_queries": [],
    "query_strategy": "hybrid",
    "target_per_platform": 200,
    "title_target_per_platform": 200,
    "deep_process_limit_per_platform": 40,
    "freshness_window_hours": 24,
    "scroll_rounds_per_query": 8,
    "scroll_stop_after_no_new_rounds": 2,
    "wait_min_seconds": 25,
    "wait_max_seconds": 60,
    "max_items_per_task": 20,
    "detail_limit_per_task": 1,
    "video_processing_priority": "asr",
    "enable_keyframes": False,
    "asr_backend": "auto",
    "asr_model": "small",
    "asr_language": "zh",
    "cooldown_minutes_on_limit": 60,
    "quality_goal": "v023_asr_first_title_pool",
    "parallel_limit": 2,
}


class CollectionConfigPayload(BaseModel):
    platforms: List[str] = Field(default_factory=lambda: ["xiaohongshu", "douyin"])
    manual_queries: List[str] = Field(default_factory=list)
    segments: List[str] = Field(default_factory=list)
    risk_terms: List[str] = Field(default_factory=list)
    opportunity_terms: List[str] = Field(default_factory=list)
    hermes_queries: List[str] = Field(default_factory=list)
    query_strategy: str = "hybrid"
    target_per_platform: int = 200
    title_target_per_platform: int = 200
    deep_process_limit_per_platform: int = 40
    freshness_window_hours: int = 24
    scroll_rounds_per_query: int = 8
    scroll_stop_after_no_new_rounds: int = 2
    wait_min_seconds: int = 25
    wait_max_seconds: int = 60
    max_items_per_task: int = 20
    detail_limit_per_task: int = 1
    video_processing_priority: str = "asr"
    enable_keyframes: bool = False
    asr_backend: str = "auto"
    asr_model: str = "small"
    asr_language: str = "zh"
    cooldown_minutes_on_limit: int = 60
    quality_goal: str = "v023_asr_first_title_pool"
    parallel_limit: int = 2


class CollectionJobRequest(BaseModel):
    platform: str = "all"
    stage: str = "all"
    mode: str = "shellCLI"
    action: str = "collect"
    run_mode: str = "manual"
    dry_run: bool = False
    queries: str = ""  # comma-separated, e.g. "阳朔 旅游,阳朔 竹筏"


class DecisionPayload(BaseModel):
    id: str
    status: str
    weight_override: int | None = None
    note: str = ""


class TrashPayload(BaseModel):
    item_type: str = "candidate"
    ids: List[str]
    reason: str = ""


class TrashRestorePayload(BaseModel):
    ids: List[str]


def create_app(store: IntelligenceStore, project_root: Path | str = ".") -> FastAPI:
    root = Path(project_root)
    app = FastAPI(title="AetherFlux V0.2.7 Admin API", version=APP_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    dist_dir = root / "dist"
    if dist_dir.exists():
        app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")

        @app.get("/")
        def admin_index() -> FileResponse:
            return FileResponse(dist_dir / "index.html")

    # ── Dashboard ──────────────────────────────────────────────

    @app.get("/api/v1/dashboard/summary")
    def dashboard_summary() -> Dict[str, Any]:
        candidates = store.list_candidates(limit=500)
        approved = [item for item in candidates if item.get("human_status") == "approved"]
        rejected = [item for item in candidates if item.get("human_status") == "rejected"]
        pending = [item for item in candidates if item.get("human_status") == "pending"]
        risks = [item for item in candidates if "风险预警" in item.get("signals", [])]
        opportunities = [item for item in candidates if "项目机会" in item.get("signals", [])]
        foreign = [item for item in candidates if item.get("language") == "en" or item.get("category") == "foreign_signal"]
        high_geo = [
            item for item in candidates
            if float((item.get("geo_risk") or {}).get("probability") or 0) >= 0.7
            or str((item.get("geo_risk") or {}).get("level", "")).lower() == "high"
        ]
        return _safe_payload(
            {
                "version": APP_VERSION_LABEL,
                "generated_at": _utc_now(),
                "counts": {
                    "candidates": len(candidates),
                    "approved": len(approved),
                    "rejected": len(rejected),
                    "pending": len(pending),
                    "risks": len(risks),
                    "opportunities": len(opportunities),
                    "foreign_signals": len(foreign),
                    "geo_high": len(high_geo),
                    "jobs": len(store.list_admin_jobs(limit=200)),
                    "trash": len(store.list_trash(limit=200)),
                },
                "guardrails": {
                    "local_only": True,
                    "auto_review_not_auto_publish": True,
                    "trash_policy": "soft_delete_restore_14_days_no_batch_physical_delete",
                    "supabase_scope": "login_and_daily_log_index_only",
                },
                "system": build_system_status(store),
            }
        )

    # ── Collection Config (file-primary, SQLite cache) ─────────

    @app.get("/api/v1/collection/config")
    def get_collection_config() -> Dict[str, Any]:
        return _safe_payload(_load_collection_config(root, store))

    @app.put("/api/v1/collection/config")
    def put_collection_config(payload: CollectionConfigPayload) -> Dict[str, Any]:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        data["parallel_limit_warning"] = data["parallel_limit"] > 2
        _save_collection_config(root, data, store)
        return _safe_payload(data)

    # ── Collection Jobs ────────────────────────────────────────

    @app.get("/api/v1/collection/jobs")
    def list_collection_jobs() -> Dict[str, Any]:
        return {"items": [_safe_payload(job) for job in store.list_admin_jobs()]}

    @app.post("/api/v1/collection/jobs")
    def create_collection_job(payload: CollectionJobRequest) -> Dict[str, Any]:
        job = _build_job(payload, root)
        store.save_admin_job(job)
        if payload.dry_run:
            _write_log(Path(job["log_path"]), "dry-run: " + " ".join(job["command"]) + "\n")
            job["status"] = "succeeded"
            job["started_at"] = _utc_now()
            job["ended_at"] = _utc_now()
            job["exit_code"] = 0
            job["log_size_bytes"] = Path(job["log_path"]).stat().st_size if Path(job["log_path"]).exists() else 0
            store.save_admin_job(job)
            return _safe_payload(job)
        # Async: spawn background thread, return immediately
        def _async_run() -> None:
            _run_job_sync(job, store)
        thread = threading.Thread(target=_async_run, daemon=True)
        thread.start()
        return _safe_payload(job)

    @app.get("/api/v1/collection/jobs/{job_id}")
    def get_collection_job(job_id: str) -> Dict[str, Any]:
        job = store.get_admin_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        return _safe_payload(job)

    @app.get("/api/v1/collection/jobs/{job_id}/log")
    def get_collection_job_log(job_id: str) -> Any:
        job = store.get_admin_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        log_path = Path(job.get("log_path", ""))
        if not log_path.exists():
            return PlainTextResponse("", status_code=200)
        content = _read_log_tail(log_path)
        return PlainTextResponse(content, status_code=200)

    @app.post("/api/v1/collection/jobs/{job_id}/cancel")
    def cancel_collection_job(job_id: str) -> Dict[str, Any]:
        job = store.get_admin_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        if job.get("status") not in {"queued", "running"}:
            return {"ok": True, "cancelled": False, "job": _safe_payload(job)}
        job["status"] = "cancelling"
        job["cancel_requested_at"] = _utc_now()
        store.save_admin_job(job)
        pid = int(job.get("pid") or 0)
        if pid:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            except PermissionError as exc:
                job["status"] = "running"
                job["error_summary"] = f"cancel_permission_denied: {exc}"
                store.save_admin_job(job)
                raise HTTPException(status_code=403, detail="permission denied while cancelling job") from exc
        else:
            job["status"] = "cancelled"
            job["ended_at"] = _utc_now()
            job["exit_code"] = -15
            job["error_summary"] = "cancelled_before_process_started"
            store.save_admin_job(job)
        return {"ok": True, "cancelled": True, "job": _safe_payload(store.get_admin_job(job_id))}

    # ── Intelligence ───────────────────────────────────────────

    @app.get("/api/v1/intelligence/candidates")
    def list_candidates() -> Dict[str, Any]:
        return {"items": [_safe_payload(item) for item in store.list_candidates(limit=300)]}

    @app.get("/api/v1/intelligence/decisions")
    def decision_candidates() -> Dict[str, Any]:
        return {"items": [_safe_payload(item) for item in store.list_candidates(limit=300)]}

    @app.post("/api/v1/intelligence/decisions")
    def set_decision(payload: DecisionPayload) -> Dict[str, Any]:
        store.set_human_decision(payload.id, payload.status, payload.weight_override, payload.note)
        return {"ok": True, "candidate": _safe_payload(store.get_candidate(payload.id))}

    @app.get("/api/v1/intelligence/selected")
    def selected() -> Dict[str, Any]:
        return {"items": [_safe_payload(item) for item in build_public_payloads(store)["selected"]]}

    @app.get("/api/v1/intelligence/daily")
    def daily() -> Dict[str, Any]:
        return _safe_payload(build_public_payloads(store)["daily"])

    @app.get("/api/v1/intelligence/opportunities")
    def opportunities() -> Dict[str, Any]:
        return {"items": [_safe_payload(item) for item in build_public_payloads(store)["opportunities"]]}

    @app.get("/api/v1/intelligence/foreign-signals")
    def foreign_signals() -> Dict[str, Any]:
        return {"items": [_safe_payload(item) for item in build_public_payloads(store)["foreign_signals"]]}

    @app.get("/api/v1/intelligence/risks")
    def risks() -> Dict[str, Any]:
        return {"items": [_safe_payload(item) for item in build_public_payloads(store)["risks"]]}

    # ── Admin ──────────────────────────────────────────────────

    @app.get("/api/v1/admin/official-sources")
    def official_sources() -> Dict[str, Any]:
        return {"items": _safe_payload(store.list_official_sources())}

    @app.post("/api/v1/admin/official-sources")
    def save_official_source(payload: Dict[str, Any]) -> Dict[str, Any]:
        store.upsert_official_source(
            str(payload.get("id", "")),
            str(payload.get("mission_id", "")),
            str(payload.get("url", "")),
            str(payload.get("label", "")),
            status=str(payload.get("status", "active")),
            recommended_by=str(payload.get("recommended_by", "manual")),
        )
        return {"ok": True, "items": store.list_official_sources(str(payload.get("mission_id", "")))}

    @app.get("/api/v1/admin/retention")
    def retention() -> Dict[str, Any]:
        return {
            "evidence_hours": store.get_retention_hours(),
            "cloud_log_months": store.get_cloud_log_months(),
            "notice": "原始截图、HTML、音视频、评论全文和完整转写不上传 Supabase Cloud。",
        }

    @app.post("/api/v1/admin/retention")
    def save_retention(payload: Dict[str, Any]) -> Dict[str, Any]:
        evidence_hours = _parse_required_int(payload, "evidence_hours", 48)
        cloud_log_months = _parse_required_int(payload, "cloud_log_months", store.get_cloud_log_months())
        store.set_retention_hours(
            evidence_hours,
            cloud_log_months=cloud_log_months,
        )
        return retention()

    # ── Bundles & Syncs ────────────────────────────────────────

    @app.get("/api/v1/daily-bundles")
    def daily_bundles() -> Dict[str, Any]:
        _sync_daily_bundles_from_inbox(store)
        return {"items": _safe_payload(store.list_daily_bundles())}

    @app.get("/api/v1/cloud-log-syncs")
    def cloud_log_syncs() -> Dict[str, Any]:
        return {"items": _safe_payload(store.list_cloud_log_syncs())}

    # ── Trash (soft-delete only) ───────────────────────────────

    @app.get("/api/v1/trash")
    def trash() -> Dict[str, Any]:
        return {"items": _safe_payload(store.list_trash())}

    @app.post("/api/v1/trash")
    def move_to_trash(payload: TrashPayload) -> Dict[str, Any]:
        return {"moved": store.move_to_trash(payload.item_type, payload.ids, payload.reason)}

    @app.post("/api/v1/trash/restore")
    def restore_trash(payload: TrashRestorePayload) -> Dict[str, Any]:
        return {"restored": store.restore_trash(payload.ids)}

    @app.post("/api/v1/trash/mark-cleanable")
    def mark_trash_cleanable() -> Dict[str, Any]:
        marked = store.mark_trash_cleanable()
        return {"marked": marked, "physical_delete_performed": False}

    # ── Title Pool & Video Processing (read-only from artifacts) ─

    @app.get("/api/v1/title-pool")
    def title_pool() -> Dict[str, Any]:
        return _safe_payload(_load_latest_artifact(
            root / "artifacts" / "opencli" / "live",
            "*_title_pool.json",
            "*_screened.json",
        ))

    @app.get("/api/v1/video-processing")
    def video_processing() -> Dict[str, Any]:
        return _safe_payload(_load_latest_artifact(
            root / "artifacts" / "opencli" / "live",
            "*_video_asr_results.json",
        ))

    # ── System ─────────────────────────────────────────────────

    @app.get("/api/v1/system/status")
    def system_status() -> Dict[str, Any]:
        return _safe_payload(
            {
                "status": build_system_status(store),
                "runtime": {
                    "python": sys.version.split()[0],
                    "platform": platform_module.platform(),
                    "project_root": str(root),
                    "triagent": {"dashboard": "triagent dashboard", "integration": "link_only"},
                },
            }
        )

    @app.post("/api/v1/system/deepseek-smoke-test")
    def deepseek_smoke_test() -> Dict[str, Any]:
        return _safe_payload(run_deepseek_smoke_test())

    @app.get("/api/v1/system/opencli-doctor")
    def opencli_doctor() -> Dict[str, Any]:
        return _run_diagnostic(["opencli", "doctor"], root)

    @app.get("/api/v1/system/diagnose")
    def system_diagnose() -> Dict[str, Any]:
        opencli = _run_diagnostic(["opencli", "doctor"], root)
        return _safe_payload(
            {
                "generated_at": _utc_now(),
                "deepseek": _run_deepseek_diagnostic(),
                "opencli": opencli,
                "runtime": {
                    "python": sys.version.split()[0],
                    "platform": platform_module.platform(),
                    "project_root": str(root),
                },
                "asr": {
                    "backend": _load_collection_config(root, store).get("asr_backend", "auto"),
                    "priority": _load_collection_config(root, store).get("video_processing_priority", "asr"),
                },
            }
        )

    # ── Agent & Release ────────────────────────────────────────

    @app.get("/api/v1/agent/apis")
    def agent_apis() -> Dict[str, Any]:
        paths = [
            "/api/v1/intelligence/selected",
            "/api/v1/intelligence/daily",
            "/api/v1/intelligence/opportunities",
            "/api/v1/intelligence/foreign-signals",
            "/api/v1/intelligence/risks",
            "/api/v1/daily-bundles",
        ]
        return {"items": [{"path": path, "method": "GET"} for path in paths], "generated_at": _utc_now()}

    @app.get("/api/v1/release/status")
    def release_status() -> Dict[str, Any]:
        changelog = _parse_changelog(root)
        return {
            "current_version": changelog["current_version"],
            "github_repo": "https://github.com/HJM-DUD/aetherflux-yangshuo",
            "changelog_url": "https://github.com/HJM-DUD/aetherflux-yangshuo/blob/main/CHANGELOG.md",
            "releases_url": "https://github.com/HJM-DUD/aetherflux-yangshuo/releases",
            "versions": changelog["versions"],
        }

    return app


# ── Helpers ────────────────────────────────────────────────────────


def _parse_changelog(root: Path) -> Dict[str, Any]:
    """Parse CHANGELOG.md into structured version data."""
    changelog_path = root / "CHANGELOG.md"
    versions: List[Dict[str, Any]] = []
    current_version = APP_VERSION_LABEL

    if not changelog_path.exists():
        return {"current_version": current_version, "versions": versions}

    try:
        text = changelog_path.read_text(encoding="utf-8")
    except OSError:
        return {"current_version": current_version, "versions": versions}

    version_re = re.compile(r'^##\s+\[(V[\d.]+)\]\s*-\s*(\d{4}-\d{2}-\d{2})', re.MULTILINE)
    section_re = re.compile(r'^###\s+(.+?)\s*/\s*(.+?)$', re.MULTILINE)
    item_re = re.compile(r'^-\s+(.+)', re.MULTILINE)

    v_matches = list(version_re.finditer(text))
    if v_matches:
        current_version = v_matches[0].group(1)

    for i, v_match in enumerate(v_matches):
        version = v_match.group(1)
        date = v_match.group(2)
        v_start = v_match.end()
        next_v = version_re.search(text, v_start)
        v_end = next_v.start() if next_v else len(text)
        v_text = text[v_start:v_end]

        sections: List[Dict[str, Any]] = []
        for s_match in section_re.finditer(v_text):
            zh_label = s_match.group(1).strip()
            s_start = s_match.end()
            next_s = section_re.search(v_text, s_start)
            s_end = next_s.start() if next_s else len(v_text)
            s_text = v_text[s_start:s_end]

            items: List[str] = []
            for item_m in item_re.finditer(s_text):
                item_text = item_m.group(1).strip()
                if item_text.startswith("`") and len(item_text) < 50:
                    continue  # skip inline code snippets
                item_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', item_text)
                item_text = re.sub(r'`([^`]+)`', r'\1', item_text)
                if len(item_text) > 3:
                    items.append(item_text)

            if items:
                sections.append({"label": zh_label, "items": items[:8]})

        if sections:
            versions.append({"version": version, "date": date, "sections": sections})

    return {"current_version": current_version, "versions": versions}


def _load_collection_config(root: Path, store: IntelligenceStore) -> Dict[str, Any]:
    """Load config from config/live_collect.json as primary source, fill defaults, cache to SQLite."""
    config_path = root / "config" / "live_collect.json"
    config: Dict[str, Any] = dict(DEFAULT_COLLECT_CONFIG)
    if config_path.exists():
        try:
            file_data = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(file_data, dict):
                config.update(file_data)
        except (json.JSONDecodeError, OSError):
            pass
    # Also sync to SQLite cache
    try:
        store.set_admin_collection_config(config)
    except Exception as exc:
        import sys
        print(f"[AetherFlux] WARNING: config cache sync failed: {exc}", file=sys.stderr)
    return config


def _save_collection_config(root: Path, data: Dict[str, Any], store: IntelligenceStore) -> None:
    """Write config to config/live_collect.json and SQLite cache."""
    config_path = root / "config" / "live_collect.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    merged = dict(DEFAULT_COLLECT_CONFIG)
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                merged.update(existing)
        except (json.JSONDecodeError, OSError):
            pass
    merged.update(data)
    config_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    store.set_admin_collection_config(merged)

    # Sync platforms + queries only to shellCLI's collect.json (E4 fix)
    _sync_collect_json(root, merged)


def _sync_collect_json(root: Path, merged: Dict[str, Any]) -> None:
    """Sync only platforms and queries to shellCLI config/collect.json, preserving other fields."""
    collect_path = root / "aetherflux_shellCLI" / "config" / "collect.json"
    collect_path.parent.mkdir(parents=True, exist_ok=True)
    shell_config: Dict[str, Any] = {}
    if collect_path.exists():
        try:
            shell_config = json.loads(collect_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    # Only overwrite platforms + queries; rest stays as-is
    shell_config["platforms"] = list(merged.get("platforms", ["xiaohongshu", "douyin"]))
    shell_config["queries"] = list(merged.get("manual_queries", merged.get("queries", ["阳朔 旅游"])))
    collect_path.write_text(json.dumps(shell_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Also sync agentCLI config (V0.2.6 fix: P1 config chain)
    agent_path = root / "aetherflux_agentCLI" / "config" / "collect.json"
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    agent_config: Dict[str, Any] = {}
    if agent_path.exists():
        try:
            agent_config = json.loads(agent_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    agent_config["platforms"] = list(merged.get("platforms", ["xiaohongshu", "douyin"]))
    agent_config["queries"] = list(merged.get("manual_queries", merged.get("queries", ["阳朔 旅游"])))
    agent_path.write_text(json.dumps(agent_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_latest_artifact(artifact_dir: Path, *globs: str) -> Dict[str, Any]:
    """Find the latest JSON file matching any glob pattern, return its contents as items."""
    if not artifact_dir.exists():
        return {"items": [], "empty_reason": "artifact_dir_missing"}
    candidates: List[Path] = []
    for g in globs:
        candidates.extend(sorted(artifact_dir.glob(g)))
    if not candidates:
        return {"items": [], "empty_reason": "no_matching_files"}
    # Pick the latest by modification time
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "items": [],
            "empty_reason": "read_error",
            "file": str(latest),
            "collected_at": datetime.fromtimestamp(latest.stat().st_mtime, timezone.utc).isoformat(),
        }
    collected_at = datetime.fromtimestamp(latest.stat().st_mtime, timezone.utc).isoformat()
    if isinstance(data, list):
        return {"items": data, "file": str(latest), "collected_at": collected_at}
    return {"items": [data], "file": str(latest), "collected_at": collected_at}


def _build_job(payload: CollectionJobRequest, root: Path) -> Dict[str, Any]:
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    log_path = root / "logs" / "admin" / f"{job_id}.log"
    command, cwd = _build_collection_command(payload, root)
    if payload.dry_run:
        command.append("--dry-run")
    return {
        "id": job_id,
        "platform": payload.platform,
        "stage": payload.stage,
        "mode": payload.mode,
        "action": payload.action,
        "run_mode": payload.run_mode,
        "status": "queued",
        "dry_run": payload.dry_run,
        "command": command,
        "cwd": str(cwd),
        "log_path": str(log_path),
        "created_at": _utc_now(),
    }


def _build_collection_command(payload: CollectionJobRequest, root: Path) -> tuple[List[str], Path]:
    mode = payload.mode
    action = payload.action
    inbox = daily_bundles_inbox_dir()

    # Parse platform overrides: comma-separated → list, "all" → empty
    platform_raw = (payload.platform or "").strip()
    platform_list: List[str] = []
    if platform_raw and platform_raw != "all":
        platform_list = [p.strip() for p in platform_raw.split(",") if p.strip()]

    # Parse query overrides: comma-separated → list
    query_raw = (payload.queries or "").strip()
    query_list: List[str] = []
    if query_raw:
        query_list = [q.strip() for q in query_raw.split(",") if q.strip()]

    if mode == "shellCLI":
        subproject = root / "aetherflux_shellCLI"
        if action == "auto_pipeline":
            return (_auto_pipeline_command("aetherflux_shellcli", "shellCLI", inbox), subproject)
        if action == "collect":
            cmd = [
                sys.executable,
                "-m",
                "aetherflux_shellcli.cli",
                "backend-hook",
                "--config",
                "config/collect.json",
                "--stage",
                "all",
                "--bundle-root",
                str(shellcli_bundle_root()),
                "--main-inbox",
                str(inbox),
            ]
            if platform_list:
                cmd.extend(["--platforms"] + platform_list)
            if query_list:
                cmd.extend(["--queries"] + query_list)
            return (cmd, subproject)
        if action == "package":
            return (_bundle_command("aetherflux_shellcli", "shellCLI", inbox), subproject)
        if action == "clean":
            return (_safe_clean_command("shellCLI", subproject), subproject)
        if action == "manual_web":
            return (_manual_web_command("shellCLI", subproject), subproject)
        raise HTTPException(status_code=400, detail=f"unsupported shellCLI action: {action}")
    if mode == "agentCLI":
        subproject = root / "aetherflux_agentCLI"
        if action == "auto_pipeline":
            return (_auto_pipeline_command("aetherflux_agentcli", "agentCLI", inbox), subproject)
        if action == "collect":
            cmd = [
                sys.executable,
                "-m",
                "aetherflux_agentcli.cli",
                "backend-hook",
                "--bundle-root",
                str(agentcli_bundle_root()),
                "--main-inbox",
                str(inbox),
            ]
            if platform_list:
                cmd.extend(["--platforms"] + platform_list)
            if query_list:
                cmd.extend(["--queries"] + query_list)
            return (cmd, subproject)
        if action == "package":
            return (_bundle_command("aetherflux_agentcli", "agentCLI", inbox), subproject)
        if action == "clean":
            return (_safe_clean_command("agentCLI", subproject), subproject)
        if action == "manual_web":
            return (_manual_web_command("agentCLI", subproject), subproject)
        raise HTTPException(status_code=400, detail=f"unsupported agentCLI action: {action}")
    raise HTTPException(status_code=400, detail=f"unsupported collection mode: {mode}")


def _manual_web_command(mode: str, subproject: Path) -> List[str]:
    message = (
        f"{mode} 手动网页启动已登记。子项目路径：{subproject}。"
        "请在对应子项目或浏览器内完成手动网页采集，后台保留任务包记录。"
    )
    return [sys.executable, "-c", f"print({message!r})"]


def _safe_clean_command(mode: str, subproject: Path) -> List[str]:
    script = (
        "import os\n" "from pathlib import Path\n"
        "root = Path.cwd()\n"
        "import os\n"
        "data_root = os.environ.get('AETHERFLUX_DATA_ROOT', '/Users/gugu/Documents/Agent/AetherFlux_Data')\n"
        "targets = [Path(data_root)]\n"
        "files = [p for target in targets if target.exists() for p in target.rglob('*') if p.is_file()]\n"
        "size = sum(p.stat().st_size for p in files)\n"
        f"print('清理扫描完成：{mode}；未执行物理删除。')\n"
        "print(f'扫描文件数：{len(files)}')\n"
        "print(f'占用磁盘：{size} bytes')\n"
    )
    return [sys.executable, "-c", script]


def _bundle_command(package_name: str, mode: str, inbox: Path) -> List[str]:
    return [sys.executable, "-c", _copy_latest_bundle_script(mode, inbox)]


def _copy_latest_bundle_script(mode: str, inbox: Path) -> str:
    return (
        "from pathlib import Path\n"
        "import os, json, shutil\n"
        "data_root = os.environ.get('AETHERFLUX_DATA_ROOT', '/Users/gugu/Documents/Agent/AetherFlux_Data')\n"
        f"bundles_root = Path(data_root) / {mode!r} / 'daily_bundles'\n"
        "if not bundles_root.exists():\n"
        "    print('无资料包目录，跳过打包。')\n"
        "    exit(0)\n"
        "candidates = sorted(bundles_root.glob('daily_bundle_*/*/manifest.json'), key=lambda p: p.stat().st_mtime, reverse=True)\n"
        "if not candidates:\n"
        "    print('未找到已有资料包，跳过打包。')\n"
        "    exit(0)\n"
        "manifest_path = candidates[0]\n"
        "latest = manifest_path.parent\n"
        "if not manifest_path.exists():\n"
        "    print(f'资料包 {latest.name} 缺少 manifest，跳过。')\n"
        "    exit(0)\n"
        "manifest = json.loads(manifest_path.read_text(encoding='utf-8'))\n"
        "counts = manifest.get('counts', {})\n"
        "total = counts.get('raw_items', 0)\n"
        "if total == 0:\n"
        "    print(f'最近资料包 {latest.name} 无采集数据（raw_items=0），跳过打包以避免生成空包。')\n"
        "    exit(0)\n"
        f"target = Path({str(inbox)!r}) / {mode!r} / manifest.get('bundle_date', 'unknown') / manifest.get('run_id', 'unknown')\n"
        "if target.exists():\n"
        "    print(f'目标路径已存在：{target}')\n"
        "    exit(0)\n"
        "target.parent.mkdir(parents=True, exist_ok=True)\n"
        "shutil.copytree(latest, target)\n"
        "print(f'已打包最近资料包：{latest.name} -> {target}')\n"
        "print(f'采集条数：raw_items={total}')\n"
    )


def _auto_pipeline_command(package_name: str, mode: str, inbox: Path) -> List[str]:
    if mode == "shellCLI":
        collect_args = [
            sys.executable,
            "-m",
            "aetherflux_shellcli.cli",
            "backend-hook",
            "--config",
            "config/collect.json",
            "--stage",
            "all",
            "--bundle-root",
            str(shellcli_bundle_root()),
            "--main-inbox",
            str(inbox),
        ]
    else:
        collect_args = [
            sys.executable,
            "-m",
            "aetherflux_agentcli.cli",
            "backend-hook",
            "--bundle-root",
            str(agentcli_bundle_root()),
            "--main-inbox",
            str(inbox),
        ]
    script = (
        "import subprocess\n"
        "from pathlib import Path\n"
        "print('第一步：启动采集任务')\n"
        f"subprocess.run({collect_args!r}, check=True)\n"
        "print('第二步：清理扫描开始（不执行物理删除）')\n"
        "root = Path.cwd()\n"
        "import os\n"
        "data_root = os.environ.get('AETHERFLUX_DATA_ROOT', '/Users/gugu/Documents/Agent/AetherFlux_Data')\n"
        "targets = [Path(data_root)]\n"
        "files = [p for target in targets if target.exists() for p in target.rglob('*') if p.is_file()]\n"
        "size = sum(p.stat().st_size for p in files)\n"
        "print(f'清理扫描完成：文件数={len(files)}；占用={size} bytes；物理删除=否')\n"
        "print('第三步：复制最近采集资料包到智脑入口')\n"
        + _copy_latest_bundle_script(mode, inbox)
    )
    return [sys.executable, "-c", script]


# _bundle_script_body removed in V0.2.5 Fix 2
# Old _bundle_script_body removed — replaced by _copy_latest_bundle_script

def _run_job_sync(job: Dict[str, Any], store: IntelligenceStore) -> None:
    latest = store.get_admin_job(str(job["id"]))
    if latest.get("status") == "cancelled":
        return
    job["status"] = "running"
    job["started_at"] = _utc_now()
    store.save_admin_job(job)
    log_path = Path(job["log_path"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as handle:
        process = subprocess.Popen(
            job["command"],
            cwd=str(job.get("cwd") or Path.cwd()),
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        job["pid"] = process.pid
        store.save_admin_job(job)
        timed_out = False
        try:
            return_code = process.wait(timeout=JOB_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            timed_out = True
            return_code = -signal.SIGTERM
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                return_code = process.wait(timeout=JOB_TERMINATE_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                return_code = -signal.SIGKILL
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
    job["ended_at"] = _utc_now()
    job["exit_code"] = return_code
    job["log_size_bytes"] = log_path.stat().st_size if log_path.exists() else 0
    latest = store.get_admin_job(str(job["id"]))
    if latest.get("status") in {"cancelling", "cancelled"}:
        job["status"] = "cancelled"
        job["cancel_requested_at"] = latest.get("cancel_requested_at")
        job["error_summary"] = "user_cancelled"
    else:
        job["status"] = "failed" if timed_out else ("succeeded" if return_code == 0 else "failed")
        if timed_out:
            job["error_summary"] = "job_timed_out_after_2h"
        elif return_code != 0:
            job["error_summary"] = f"exit_code={return_code}"
    store.save_admin_job(job)
    if job["status"] == "succeeded":
        _sync_daily_bundles_from_inbox(store)


def _read_log_tail(log_path: Path, limit_bytes: int = JOB_LOG_TAIL_BYTES) -> str:
    size = log_path.stat().st_size
    with log_path.open("rb") as handle:
        if size <= limit_bytes:
            return handle.read().decode("utf-8", errors="replace")
        handle.seek(-limit_bytes, os.SEEK_END)
        tail = handle.read().decode("utf-8", errors="replace")
    return f"(truncated: showing last {limit_bytes} of {size} bytes)\n{tail}"


def _parse_required_int(payload: Mapping[str, Any], key: str, default: int) -> int:
    value = payload.get(key, default)
    if value is None or value == "":
        raise HTTPException(status_code=422, detail=f"{key} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{key} must be an integer") from exc


def _sync_daily_bundles_from_inbox(store: IntelligenceStore) -> int:
    inbox = daily_bundles_inbox_dir()
    synced = 0
    if not inbox.exists():
        return synced
    for manifest_path in sorted(inbox.glob("*/*/*/manifest.json")):
        bundle_dir = manifest_path.parent
        try:
            manifest_bytes = manifest_path.read_bytes()
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(manifest, dict):
            continue
        run_id = str(manifest.get("run_id") or bundle_dir.name)
        bundle_date = str(manifest.get("bundle_date") or bundle_dir.parent.name)
        mode = str(manifest.get("mode") or bundle_dir.parent.parent.name)
        size_bytes = 0
        try:
            size_bytes = sum(path.stat().st_size for path in bundle_dir.iterdir() if path.is_file())
        except OSError:
            size_bytes = 0
        store.save_daily_bundle(
            {
                "id": f"{mode}:{bundle_date}:{run_id}",
                "bundle_date": bundle_date,
                "node_id": str(manifest.get("node_id") or mode),
                "path": str(bundle_dir),
                "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "size_bytes": size_bytes,
                "manifest_json": manifest,
                "cloud_log_status": "pending",
            }
        )
        synced += 1
    return synced


def _run_diagnostic(command: List[str], cwd: Path) -> Dict[str, Any]:
    try:
        process = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, timeout=60, check=False)
    except FileNotFoundError:
        return {"ok": False, "error": "command_not_found", "command": command}
    return {
        "ok": process.returncode == 0,
        "command": command,
        "exit_code": process.returncode,
        "stdout": process.stdout[-4000:],
        "stderr": process.stderr[-4000:],
    }


def _run_deepseek_diagnostic() -> Dict[str, Any]:
    try:
        return run_deepseek_smoke_test()
    except Exception as exc:
        return {"ok": False, "error": "deepseek_smoke_test_failed", "message": str(exc)}


def _write_log(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _safe_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        safe: Dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(secret in lowered for secret in ("api_key", "cookie", "token", "password", "secret")):
                continue
            safe[key] = _safe_payload(item)
        return safe
    if isinstance(value, list):
        return [_safe_payload(item) for item in value]
    if isinstance(value, str) and _is_http_url(value):
        return _safe_string(value)
    if isinstance(value, str) and _looks_like_token(value):
        return "redacted"
    return value


# Patterns that look like API keys/tokens in values
_SENSITIVE_VALUE_PATTERNS = [
    "sk-[a-zA-Z0-9]{20,}",
    "sk-ant-[a-zA-Z0-9_-]+",
    "Bearer [a-zA-Z0-9._-]{20,}",
    "dsk-[a-zA-Z0-9]{20,}",
    "(?i)[a-z0-9_]*api_key",
]

def _looks_like_token(value: str) -> bool:
    import re as _re
    return any(_re.search(p, value) for p in _SENSITIVE_VALUE_PATTERNS)


def _safe_string(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        kept_query = [
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not _looks_sensitive(key) and not _looks_sensitive(item)
        ]
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(kept_query), parsed.fragment))
    return "redacted"


def _is_http_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _looks_sensitive(value: str) -> bool:
    lowered = value.lower()
    return any(secret in lowered for secret in ("api_key", "cookie", "token", "password", "secret"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
