"""Agent-led OpenCLI collection workflow for agentCLI mode."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Sequence
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from .agent_adapter import AgentCommandTemplate, default_agent_payload
from .bundle import BundleWriter, copy_bundle_to_inbox
from .media_asr import ASRConfig, Transcriber, process_video_item
from .platforms import plan_supported_tasks
from .safety import ActionSafety, ALLOWED_ACTIONS, classify_action


Runner = Callable[..., subprocess.CompletedProcess]
DOUYIN_BROWSER_SESSION = "aetherflux-agentcli-douyin"
XIAOHONGSHU_BROWSER_SESSION = "aetherflux-agentcli-xiaohongshu"



import os as _os
from pathlib import Path as _Path
_DATA_ROOT = _Path(_os.environ.get("AETHERFLUX_DATA_ROOT", "/Users/gugu/Documents/Agent/AetherFlux_Data"))

@dataclass
class AgentCollectionConfig:
    platforms: List[str] | None = None
    queries: List[str] | None = None
    target_per_platform: int = 1
    max_items_per_task: int = 20
    freshness_window_hours: int = 24
    scroll_rounds_per_query: int = 4
    wait_seconds: int = 2
    bundle_root: str | Path = str(_DATA_ROOT / "agentCLI" / "daily_bundles")
    artifact_root: str | Path = str(_DATA_ROOT / "artifacts" / "opencli" / "agent")
    log_root: str | Path = str(_DATA_ROOT / "logs" / "opencli" / "agent")
    main_inbox: str | Path = ""
    agent_config: str | Path = "config/agents.json"
    media_root: str | Path = str(_DATA_ROOT / "artifacts" / "media" / "agent")
    asr_backend: str = "auto"
    asr_model: str = "small"
    asr_language: str = "zh"
    yt_dlp_cookies_from_browser: str = ""
    node_id: str = "local"
    place: str = "阳朔"
    industry: str = "旅游"

    def normalized_platforms(self) -> List[str]:
        return list(self.platforms or ["xiaohongshu", "douyin", "shipinghao"])

    def normalized_queries(self) -> List[str]:
        return list(self.queries or ["阳朔 旅游"])


def load_config(path: str | Path) -> AgentCollectionConfig:
    target = Path(path)
    if not target.exists():
        return AgentCollectionConfig()
    raw = json.loads(target.read_text(encoding="utf-8"))
    return AgentCollectionConfig(
        platforms=list(raw.get("platforms", ["xiaohongshu", "douyin", "shipinghao"])),
        queries=list(raw.get("queries") or raw.get("manual_queries") or ["阳朔 旅游"]),
        target_per_platform=int(raw.get("target_per_platform", 1)),
        max_items_per_task=int(raw.get("max_items_per_task", 20)),
        freshness_window_hours=int(raw.get("freshness_window_hours", 24)),
        scroll_rounds_per_query=int(raw.get("scroll_rounds_per_query", 4)),
        wait_seconds=int(raw.get("wait_seconds", raw.get("wait_min_seconds", 2))),
        bundle_root=raw.get("bundle_root", str(_DATA_ROOT / "agentCLI" / "daily_bundles")),
        artifact_root=raw.get("artifact_root", str(_DATA_ROOT / "artifacts" / "opencli" / "agent")),
        log_root=raw.get("log_root", str(_DATA_ROOT / "logs" / "opencli" / "agent")),
        main_inbox=raw.get("main_inbox", ""),
        agent_config=raw.get("agent_config", "config/agents.json"),
        media_root=raw.get("media_root", str(_DATA_ROOT / "artifacts" / "media" / "agent")),
        asr_backend=raw.get("asr_backend", "auto"),
        asr_model=raw.get("asr_model", "small"),
        asr_language=raw.get("asr_language", "zh"),
        yt_dlp_cookies_from_browser=raw.get("yt_dlp_cookies_from_browser", ""),
        node_id=raw.get("node_id", "local"),
        place=raw.get("place", "阳朔"),
        industry=raw.get("industry", "旅游"),
    )


def commands_for_task(
    platform: str,
    query: str,
    limit: int,
    freshness_window_hours: int = 24,
    scroll_rounds: int = 4,
) -> List[List[str]]:
    if platform == "xiaohongshu":
        return [
            [
                "opencli",
                "browser",
                XIAOHONGSHU_BROWSER_SESSION,
                "--window",
                "foreground",
                "open",
                f"https://www.xiaohongshu.com/search_result?keyword={quote(query)}",
            ],
            ["opencli", "browser", XIAOHONGSHU_BROWSER_SESSION, "wait", "time", "3"],
            ["opencli", "browser", XIAOHONGSHU_BROWSER_SESSION, "eval", _apply_recent_filter_js("xiaohongshu")],
            ["opencli", "browser", XIAOHONGSHU_BROWSER_SESSION, "wait", "time", "2"],
            [
                "opencli",
                "browser",
                XIAOHONGSHU_BROWSER_SESSION,
                "eval",
                _search_extract_js("xiaohongshu", query, limit, freshness_window_hours, scroll_rounds),
            ],
        ]
    if platform == "douyin":
        default_url = f"https://www.douyin.com/search/{quote(query)}?type=general"
        recent_url = f"https://www.douyin.com/search/{quote(query)}?type=general&sort_type=2&publish_time=1"
        return [
            [
                "opencli",
                "browser",
                DOUYIN_BROWSER_SESSION,
                "--window",
                "foreground",
                "open",
                recent_url,
            ],
            ["opencli", "browser", DOUYIN_BROWSER_SESSION, "wait", "time", "5"],
            ["opencli", "browser", DOUYIN_BROWSER_SESSION, "eval", _douyin_recent_url_retry_js(default_url)],
            ["opencli", "browser", DOUYIN_BROWSER_SESSION, "wait", "time", "5"],
            ["opencli", "browser", DOUYIN_BROWSER_SESSION, "eval", _apply_recent_filter_js("douyin")],
            ["opencli", "browser", DOUYIN_BROWSER_SESSION, "wait", "time", "2"],
            [
                "opencli",
                "browser",
                DOUYIN_BROWSER_SESSION,
                "eval",
                _search_extract_js("douyin", query, limit, freshness_window_hours, scroll_rounds),
            ],
        ]
    raise ValueError(f"Unsupported platform: {platform}")


def run_agent_collection(
    config: AgentCollectionConfig,
    runner: Runner = subprocess.run,
    agent_runner: Runner = subprocess.run,
    sleep_enabled: bool = True,
    stage: str = "all",
    platforms_override: List[str] | None = None,
    queries_override: List[str] | None = None,
    transcriber: Transcriber | None = None,
) -> Dict[str, Any]:
    doctor = runner(["opencli", "doctor"], check=False, capture_output=True, text=True, timeout=60)
    doctor_output = f"{doctor.stdout or ''}\n{doctor.stderr or ''}".strip()
    if doctor.returncode != 0 or "Everything looks good" not in doctor_output:
        return {"ok": False, "error": "opencli_doctor_failed", "message": doctor_output}

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle_date = datetime.now(timezone.utc).date().isoformat()
    effective_platforms = platforms_override if platforms_override else config.normalized_platforms()
    effective_queries = queries_override if queries_override else config.normalized_queries()
    tasks, placeholder_errors = plan_supported_tasks(
        effective_platforms,
        effective_queries,
        per_platform=config.target_per_platform,
    )

    artifact_root = Path(config.artifact_root)
    log_root = Path(config.log_root)
    artifact_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)

    raw_items: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = [dict(error) for error in placeholder_errors]
    agent_decisions: List[Dict[str, Any]] = []

    for task in tasks:
        platform = str(task["platform"])
        query = str(task["query"])
        task_prefix = f"{run_id}_{platform}_{int(task['task_index']):04d}"
        decision = _decide_task_with_agent(config, platform, query, agent_runner)
        agent_decisions.append(decision)
        if decision.get("decision") in {"NEED_HUMAN", "STOP"}:
            errors.append(
                {
                    "platform": platform,
                    "query": query,
                    "status": decision.get("error_status", "need_human"),
                    "message": decision.get("reason", ""),
                }
            )
            continue

        commands = commands_for_task(
            platform,
            query,
            limit=config.max_items_per_task,
            freshness_window_hours=config.freshness_window_hours,
            scroll_rounds=config.scroll_rounds_per_query,
        )
        try:
            result = _run_sequence(commands, runner)
        finally:
            _close_browser_session(platform, runner)
        (log_root / f"{task_prefix}.log").write_text((result["stdout"] + "\n" + result["stderr"]).strip(), encoding="utf-8")
        if not result["ok"]:
            errors.append({"platform": platform, "query": query, "status": _map_error(result["stderr"] or result["stdout"])})
            continue
        rows = _parse_opencli_json(result["stdout"])
        items = [_normalize_item(platform, query, row) for row in rows]
        (artifact_root / f"{task_prefix}.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        if not items:
            errors.append({"platform": platform, "query": query, "status": "empty_result"})
        raw_items.extend(items)
        if sleep_enabled:
            time.sleep(max(0, int(config.wait_seconds)))

    screened_items = _screen_items(raw_items) if stage in {"screen", "videos", "all"} else []
    asr_results = _process_asr_results(screened_items, config, run_id, runner, transcriber) if stage in {"videos", "all"} else []
    bundle = BundleWriter(config.bundle_root, mode="agentCLI", node_id=config.node_id).create_bundle(
        bundle_date=bundle_date,
        run_id=run_id,
        mission={"place": config.place, "industry": config.industry, "stage": stage},
        raw_items=raw_items,
        screened_items=screened_items,
        asr_results=asr_results,
        agent_decisions=agent_decisions,
        errors=errors,
    )
    copied = copy_bundle_to_inbox(bundle.path, config.main_inbox) if config.main_inbox else None
    return {
        "ok": True,
        "mode": "agentCLI",
        "run_id": run_id,
        "bundle": str(bundle.path),
        "copied_to": str(copied) if copied else "",
        "counts": bundle.manifest["counts"],
        "errors": errors,
    }


def _decide_task_with_agent(
    config: AgentCollectionConfig,
    platform: str,
    query: str,
    agent_runner: Runner,
) -> Dict[str, Any]:
    observation = {
        "platform": platform,
        "query": query,
        "goal": "采集当日公开可见旅游情报，先筛选最新发布/一天内，再提取标题、正文、作者、链接和发布时间。",
        "safety_boundary": "只允许公开浏览、滚动、筛选和提取；遇到登录、验证码、账号设置、发布、支付、删除、上传必须停止。",
    }
    template = _load_default_agent_template(config.agent_config)
    if not template:
        return {
            "agent": "unconfigured",
            "decision": "NEED_HUMAN",
            "reason": "agentCLI 没有可用 agent 命令配置，已停止采集。",
            "error_status": "agent_not_configured",
        }
    payload = default_agent_payload("browser_operator", observation, sorted(ALLOWED_ACTIONS))
    try:
        result = agent_runner(template.render(payload), check=False, capture_output=True, text=True, timeout=template.timeout_seconds)
    except FileNotFoundError:
        return {
            "agent": template.name,
            "decision": "NEED_HUMAN",
            "reason": "Hermes 命令不可用，agentCLI 已停止采集。",
            "error_status": "agent_unavailable",
        }
    except subprocess.TimeoutExpired:
        return {
            "agent": template.name,
            "decision": "NEED_HUMAN",
            "reason": "agent 命令被外部超时中断，agentCLI 已停止采集。",
            "error_status": "agent_interrupted",
        }
    parsed = _parse_agent_decision(result.stdout or "")
    if not parsed:
        return {
            "agent": template.name,
            "decision": "NEED_HUMAN",
            "reason": "Hermes 未返回合法 JSON 决策，agentCLI 已停止采集，不执行本地接管。",
            "error_status": "agent_decision_invalid",
            "agent_returncode": result.returncode,
        }
    decision = _normalize_agent_decision(parsed, template.name)
    actions = _decision_actions(decision)
    unsafe = [action for action in actions if classify_action(action) != ActionSafety.ALLOWED]
    if unsafe:
        return {
            "agent": template.name,
            "decision": "NEED_HUMAN",
            "reason": "agent 请求了越界动作，已停止。",
            "blocked_actions": unsafe,
        }
    return decision


def _load_default_agent_template(path: str | Path) -> AgentCommandTemplate | None:
    target = Path(path)
    if not target.exists():
        return None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        default_name = raw.get("default_agent", "hermes")
        agent = raw.get("agents", {}).get(default_name, {})
        command = list(agent.get("command", []))
        if not command:
            return None
        return AgentCommandTemplate(
            name=str(default_name),
            command=command,
            timeout_seconds=_parse_agent_timeout(agent.get("timeout_seconds")),
        )
    except (OSError, ValueError, TypeError):
        return None


def _parse_agent_timeout(value: Any) -> int | None:
    if value in (None, "", 0, "0", "none", "None", "null"):
        return None
    return int(value)


def _parse_agent_decision(stdout: str) -> Dict[str, Any] | None:
    text = (stdout or "").strip()
    if not text:
        return None
    data = _loads_json_object(text)
    if data is None:
        data = _loads_json_object(_strip_json_fence(text))
    if data is None:
        data = _loads_json_object(_extract_first_json_object(text))
    return dict(data) if isinstance(data, Mapping) else None


def _loads_json_object(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_first_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""
    return text[start : end + 1]


def _normalize_agent_decision(data: Mapping[str, Any], agent: str) -> Dict[str, Any]:
    decision = str(data.get("decision") or "APPROVED")
    if decision not in {"APPROVED", "NEED_HUMAN", "RETRY_WITH_ACTION", "STOP"}:
        decision = "NEED_HUMAN"
    return {
        "agent": agent,
        "decision": decision,
        "reason": str(data.get("reason") or ""),
        "action_payload": dict(data.get("action_payload") or {}),
        "extracted_items": list(data.get("extracted_items") or []),
    }


def _decision_actions(decision: Mapping[str, Any]) -> List[Mapping[str, object]]:
    payload = decision.get("action_payload")
    if not isinstance(payload, Mapping):
        return []
    actions = payload.get("actions")
    if isinstance(actions, list):
        return [action for action in actions if isinstance(action, Mapping)]
    action = payload.get("action")
    if action:
        return [payload]
    return []


def _run_sequence(commands: Sequence[Sequence[str]], runner: Runner) -> Dict[str, Any]:
    stdout_parts: List[str] = []
    stderr_parts: List[str] = []
    last_stdout = ""
    for command in commands:
        try:
            result = runner(list(command), check=False, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            return {"ok": False, "stdout": "\n".join(stdout_parts), "stderr": "\n".join(stderr_parts), "error": "timeout"}
        except FileNotFoundError:
            return {"ok": False, "stdout": "\n".join(stdout_parts), "stderr": "\n".join(stderr_parts), "error": "not_found"}
        stdout_parts.append(result.stdout or "")
        stderr_parts.append(result.stderr or "")
        last_stdout = result.stdout or ""
        if result.returncode != 0:
            return {
                "ok": False,
                "stdout": "\n".join(stdout_parts),
                "stderr": "\n".join(stderr_parts),
                "returncode": result.returncode,
            }
    return {"ok": True, "stdout": last_stdout, "stderr": "\n".join(stderr_parts), "returncode": 0}


def _close_browser_session(platform: str, runner: Runner) -> None:
    session = {
        "xiaohongshu": XIAOHONGSHU_BROWSER_SESSION,
        "douyin": DOUYIN_BROWSER_SESSION,
    }.get(platform)
    if not session:
        return
    try:
        runner(["opencli", "browser", session, "close"], check=False, capture_output=True, text=True, timeout=30)
    except Exception:
        return


def _parse_opencli_json(stdout: str) -> List[Dict[str, Any]]:
    text = (stdout or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [dict(row) for row in data if isinstance(row, Mapping)]
    if isinstance(data, Mapping):
        for key in ("rows", "data", "items", "result"):
            value = data.get(key)
            if isinstance(value, list):
                return [dict(row) for row in value if isinstance(row, Mapping)]
        return [dict(data)]
    return []


def _normalize_item(platform: str, query: str, row: Mapping[str, Any]) -> Dict[str, Any]:
    title = _clean(row.get("title") or row.get("text") or row.get("name"))
    url = _sanitize_url(_clean(row.get("url")))
    item_id = _clean(row.get("id") or row.get("content_id") or url or f"{platform}:{query}:{title}")
    quality_status = "rejected" if _is_boilerplate(title, url) else ("accepted" if title else "rejected")
    reject_reason = "navigation_or_boilerplate" if _is_boilerplate(title, url) else ("" if title else "missing_title")
    raw_time = _clean(row.get("published_at_raw") or row.get("published_at"))
    if quality_status == "accepted" and not raw_time:
        quality_status = "rejected"
        reject_reason = "missing_published_time"
    if quality_status == "accepted" and _is_obviously_stale(raw_time):
        quality_status = "rejected"
        reject_reason = "outside_today_or_24h_window"
    return {
        "item_id": item_id,
        "hard_dedupe_key": f"{platform}:url:{url}" if url else f"{platform}:title:{title}",
        "topic_cluster_key": f"{query}:{title[:20]}",
        "platform": platform,
        "query": query,
        "title": title,
        "body": _clean(row.get("body") or row.get("description") or row.get("text") or title),
        "url": url,
        "author": _clean(row.get("author")),
        "published_at": _clean(row.get("published_at")),
        "published_at_raw": raw_time,
        "duration": _clean(row.get("duration")),
        "content_type": _clean(row.get("content_type") or ("video" if _clean(row.get("duration")) else "")),
        "ui_filter_applied": bool(row.get("ui_filter_applied")),
        "filter_labels": list(row.get("filter_labels") or []),
        "source_page": _sanitize_url(_clean(row.get("source_page"))),
        "engagement": {"likes": _to_int(row.get("likes")), "comments": _to_int(row.get("comments"))},
        "capture_method": "agentcli_opencli_browser_bridge",
        "priority_level": "T3",
        "quality_status": quality_status,
        "reject_reason": reject_reason,
    }


def _screen_items(items: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    screened = []
    for item in items:
        if item.get("quality_status") != "accepted":
            continue
        screened.append(
            {
                "item_id": item.get("item_id"),
                "platform": item.get("platform"),
                "query": item.get("query"),
                "title": item.get("title"),
                "body": item.get("body"),
                "url": item.get("url"),
                "author": item.get("author"),
                "published_at_raw": item.get("published_at_raw"),
                "duration": item.get("duration"),
                "content_type": item.get("content_type"),
                "decision": "APPROVED",
                "decision_source": "agentcli_agent_rules",
                "reason": "agentCLI 已按最新/一天内公开结果完成初筛。",
            }
        )
    return screened


def _process_asr_results(
    items: Sequence[Mapping[str, Any]],
    config: AgentCollectionConfig,
    run_id: str,
    runner: Runner,
    transcriber: Transcriber | None,
) -> List[Dict[str, Any]]:
    media_root = Path(config.media_root) / run_id[:8] / run_id
    asr_config = ASRConfig(
        backend=config.asr_backend,
        model=config.asr_model,
        language=config.asr_language,
        cookies_from_browser=config.yt_dlp_cookies_from_browser,
    )
    return [process_video_item(item, media_root, config=asr_config, runner=runner, transcriber=transcriber) for item in items]


def _map_error(message: str) -> str:
    text = message.lower()
    if "login" in text or "auth" in text or "登录" in text:
        return "auth_required"
    if "security" in text or "验证码" in text or "安全" in text:
        return "security_block"
    if "empty" in text or "no rows" in text:
        return "empty_result"
    return "command_failed"


def _apply_recent_filter_js(platform: str) -> str:
    platform_json = json.dumps(platform)
    return f"""
(async () => {{
  const platform = {platform_json};
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const clickedLabels = platform === "douyin" && window.__aetherflux_douyin_recent_url_effective ? ["最新发布", "一天内"] : [];
  const textOf = (node) => (node.innerText || node.textContent || "").replace(/\\s+/g, " ").trim();
  const clickNode = async (node, label) => {{
    try {{
      node.scrollIntoView?.({{ block: "center", inline: "center" }});
      node.click();
      clickedLabels.push(label);
      await wait(500);
      return true;
    }} catch (_err) {{
      return false;
    }}
  }};
  const clickFilter = async () => {{
    const filterNode = document.querySelector(".filter") || Array.from(document.querySelectorAll("button, div, span, a")).find((node) => textOf(node) === "筛选" || textOf(node).startsWith("筛选 "));
    return filterNode ? clickNode(filterNode, "筛选") : false;
  }};
  const clickText = async (labels) => {{
    for (const label of labels) {{
      const nodes = Array.from(document.querySelectorAll("button, div, span, a"))
        .filter((node) => {{
          const text = textOf(node);
          if (!text) return false;
          return text === label;
        }});
      for (const node of nodes.slice(0, 4)) {{
        if (await clickNode(node, label)) return true;
      }}
    }}
    return false;
  }};
  await clickFilter();
  await wait(800);
  if (platform === "xiaohongshu") {{
    await clickText(["最新"]);
  }} else {{
    await clickText(["最新发布", "最新"]);
  }}
  await wait(500);
  await clickText(["一天内", "24小时内", "今天"]);
  await wait(800);
  window.__aetherflux_recent_filter_applied = clickedLabels.length > 0;
  window.__aetherflux_recent_filter_labels = clickedLabels;
  return JSON.stringify([{{ platform, ui_filter_applied: clickedLabels.length > 0, filter_labels: clickedLabels, source_page: location.href }}]);
}})()
""".strip()


def _douyin_recent_url_retry_js(default_url: str) -> str:
    default_url_json = json.dumps(default_url)
    return f"""
(() => {{
  const defaultUrl = {default_url_json};
  const body = document.body?.innerText || "";
  const cardCount = document.querySelectorAll('.search-result-card, [class*="search-result-card"]').length;
  const needsFallback = cardCount === 0 && /登录后即可搜索|一键登录|登录其他账号/.test(body);
  window.__aetherflux_douyin_recent_url_retry = needsFallback;
  window.__aetherflux_douyin_recent_url_effective = !needsFallback && cardCount > 0;
  if (needsFallback) {{
    location.href = defaultUrl;
    return JSON.stringify([{{ platform: "douyin", recent_url_retry: true, source_page: location.href }}]);
  }}
  return JSON.stringify([{{ platform: "douyin", recent_url_retry: false, source_page: location.href }}]);
}})()
""".strip()


def _search_extract_js(platform: str, query: str, limit: int, freshness_window_hours: int, scroll_rounds: int) -> str:
    platform_json = json.dumps(platform)
    query_json = json.dumps(query, ensure_ascii=False)
    return f"""
(async () => {{
  const platform = {platform_json};
  const query = {query_json};
  const maxRows = {int(limit)};
  const scrollRounds = {int(scroll_rounds)};
  const freshnessWindowHours = {int(freshness_window_hours)};
  const seen = new Set();
  const rows = [];
  const normalizeText = (value) => (value || "").replace(/\\s+/g, " ").trim();
  const isBadTitle = (title) => !title || title.length > 120 || /ICP备|营业执照|举报|首页|发布视频|账号找回|隐私政策|读屏标签/.test(title);
  const collectXhs = () => {{
    for (const titleLink of Array.from(document.querySelectorAll('a.title[href*="/search_result/"], a.title[href*="/explore/"]'))) {{
      if (rows.length >= maxRows) break;
      const title = normalizeText(titleLink.innerText || titleLink.textContent || "");
      if (isBadTitle(title)) continue;
      const href = new URL(titleLink.getAttribute("href"), location.href).href;
      const root = titleLink.closest(".note-item, section, article, div") || titleLink.parentElement;
      const authorNode = root?.querySelector("a.author, .author, .name") || null;
      const rawAuthorText = authorNode?.innerText || authorNode?.textContent || "";
      const authorParts = rawAuthorText.split(/\\n+/).map((part) => part.trim()).filter(Boolean);
      const body = normalizeText(root?.innerText || root?.textContent || title);
      const key = href + "::" + title;
      if (seen.has(key)) continue;
      seen.add(key);
      rows.push({{
        platform, query, title, body, url: href,
        author: authorParts[0] || "",
        likes: "", comments: "",
        published_at_raw: authorParts[1] || "",
        freshness_window_hours: freshnessWindowHours,
        ui_filter_applied: Boolean(window.__aetherflux_recent_filter_applied),
        filter_labels: window.__aetherflux_recent_filter_labels || [],
        source_page: location.href
      }});
    }}
  }};
  const collectDouyin = () => {{
    const contentIdFrom = (node) => {{
      const idNode = node?.closest?.('[id^="waterfall_item_"]');
      const rawId = idNode?.id || "";
      return rawId.replace(/^waterfall_item_/, "");
    }};
    const parseDouyinCardText = (rawText, candidateUrl = "", contentId = "") => {{
      const lines = (rawText || "").split(/\\n+/).map((part) => part.trim()).filter(Boolean);
      const compact = normalizeText(rawText);
      const authorLine = lines.find((line) => /^@/.test(line)) || "";
      const timeLine = lines.find((line) => /^·?\\s*((?:\\d+\\s*)?(?:分钟前|小时前|天前)|昨天.*|今天.*|\\d{{1,2}}月\\d{{1,2}}日|\\d{{4}}-\\d{{1,2}}-\\d{{1,2}})\\s*$/.test(line)) || "";
      const titleLine = lines.find((line) => {{
        if (/^@/.test(line)) return false;
        if (/^·/.test(line)) return false;
        if (/^\\d{{1,2}}:\\d{{2}}/.test(line)) return false;
        if (/^\\d+(\\.\\d+)?万?$/.test(line)) return false;
        if (/分钟前|小时前|天前|昨天|今天/.test(line)) return false;
        return line.length >= 4 && !isBadTitle(line);
      }}) || compact;
      const timeSource = timeLine || compact;
      const timeMatch = timeSource.match(/(?:^|·\\s*)((?:\\d+\\s*)?(?:分钟前|小时前|天前)|昨天[^ ]*|今天[^ ]*|\\d{{1,2}}月\\d{{1,2}}日|\\d{{4}}-\\d{{1,2}}-\\d{{1,2}})/);
      const durationLine = lines.find((line) => /^\\d{{1,2}}:\\d{{2}}/.test(line)) || "";
      const contentType = durationLine ? "video" : "image";
      const likeLine = lines.find((line) => /^\\d+(\\.\\d+)?万?$/.test(line)) || "";
      const author = authorLine.replace(/^@/, "").trim();
      const publishedAtRaw = timeMatch ? timeMatch[1].replace(/\\s+/g, "") : "";
      const safeTitle = normalizeText(titleLine).slice(0, 110);
      const idSeed = contentId || [platform, query, safeTitle, author, publishedAtRaw].join("::");
      let hash = 0;
      for (let i = 0; i < idSeed.length; i++) hash = ((hash << 5) - hash + idSeed.charCodeAt(i)) | 0;
      const resolvedUrl = candidateUrl || (contentId ? `https://www.douyin.com/${{contentType === "video" ? "video" : "note"}}/${{contentId}}` : "");
      return {{
        title: safeTitle,
        body: compact.slice(0, 500),
        author,
        likes: likeLine,
        comments: "",
        published_at_raw: publishedAtRaw,
        duration: durationLine,
        content_type: contentType,
        url: resolvedUrl,
        id: contentId ? "douyin:" + contentId : "douyin:" + Math.abs(hash).toString(36)
      }};
    }};
    const pushDouyinRow = (parsed) => {{
      if (rows.length >= maxRows) return;
      if (isBadTitle(parsed.title)) return;
      const key = parsed.id + "::" + parsed.title;
      if (seen.has(key)) return;
      seen.add(key);
      rows.push({{
        platform, query,
        id: parsed.id,
        title: parsed.title,
        body: parsed.body,
        url: parsed.url,
        author: parsed.author,
        likes: parsed.likes,
        comments: parsed.comments,
        published_at_raw: parsed.published_at_raw,
        duration: parsed.duration,
        content_type: parsed.content_type,
        freshness_window_hours: freshnessWindowHours,
        ui_filter_applied: Boolean(window.__aetherflux_recent_filter_applied),
        filter_labels: window.__aetherflux_recent_filter_labels || [],
        source_page: location.href
      }});
    }};
    const cards = Array.from(document.querySelectorAll('.search-result-card, [class*="search-result-card"]'));
    for (const card of cards) {{
      const link = card.querySelector('a[href*="douyin.com/video/"], a[href^="/video/"]');
      const href = link ? new URL(link.getAttribute("href"), location.href).href : "";
      pushDouyinRow(parseDouyinCardText(card.innerText || card.textContent || "", href, contentIdFrom(card)));
    }}
    const anchors = Array.from(document.querySelectorAll('a[href*="douyin.com/video/"], a[href^="/video/"]'));
    for (const link of anchors) {{
      if (rows.length >= maxRows) break;
      const href = new URL(link.getAttribute("href"), location.href).href;
      const root = link.closest(".search-result-card, [class*='search-result-card'], section, article, div") || link.parentElement;
      pushDouyinRow(parseDouyinCardText(root?.innerText || root?.textContent || link.innerText || "", href, contentIdFrom(root)));
    }}
  }};
  const collect = () => {{
    if (platform === "xiaohongshu") collectXhs();
    if (platform === "douyin") collectDouyin();
  }};
  for (let i = 0; i < scrollRounds && rows.length < maxRows; i++) {{
    collect();
    window.scrollBy(0, Math.max(600, window.innerHeight * 0.8));
    await new Promise((resolve) => setTimeout(resolve, 800));
  }}
  collect();
  return JSON.stringify(rows.slice(0, maxRows));
}})()
""".strip()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _to_int(value: Any) -> int:
    text = str(value or "0").replace(",", "").replace("，", "").strip()
    try:
        if text.endswith("万"):
            return int(float(text[:-1]) * 10000)
        if text.lower().endswith("k"):
            return int(float(text[:-1]) * 1000)
        return int(float(text))
    except ValueError:
        return 0


def _is_boilerplate(title: str, url: str) -> bool:
    text = f"{title} {url}"
    if len(title) > 120:
        return True
    return any(term in text for term in ("ICP备", "营业执照", "违法不良信息举报", "读屏标签", "账号找回", "隐私政策", "发布视频/图文", "相关搜索"))


def _sanitize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlsplit(url)
    blocked = {"xsec_token", "xsec_source", "token", "auth", "cookie", "session"}
    safe_query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key.lower() not in blocked]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(safe_query), ""))


def _is_obviously_stale(raw_time: str) -> bool:
    text = raw_time.strip()
    if not text:
        return False
    if "昨天" in text:
        return True
    if "天前" in text:
        digits = "".join(char for char in text if char.isdigit())
        return True if not digits else int(digits) >= 1
    if any(char in text for char in ("年", "-")):
        return True
    if "月" in text and "日" in text:
        return True
    return False
