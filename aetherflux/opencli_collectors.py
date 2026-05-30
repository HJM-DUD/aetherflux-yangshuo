"""OpenCLI Browser Bridge collectors for live public intelligence."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Sequence
from urllib.parse import quote

from .asr_pipeline import ASRConfig, process_video_item
from .freshness import evaluate_freshness
from .live_rotation import build_rotation_plan, load_live_collect_config
from .paths import opencli_live_log_dir, opencli_live_output_dir, opencli_media_dir
from .quality import classify_quality


Runner = Callable[..., subprocess.CompletedProcess]
DOUYIN_JINGXUAN_URL = "https://www.douyin.com/jingxuan"
DOUYIN_BROWSER_SESSION = "aetherflux-douyin"
XIAOHONGSHU_BROWSER_SESSION = "aetherflux-xiaohongshu"


@dataclass
class OpenCLIResult:
    ok: bool
    rows: List[Dict[str, Any]]
    stdout: str
    stderr: str
    returncode: int


def run_opencli_command(command: Sequence[str], runner: Runner = subprocess.run, timeout: int = 180) -> OpenCLIResult:
    result = runner(list(command), check=False, capture_output=True, text=True, timeout=timeout)
    rows: List[Dict[str, Any]] = []
    if result.returncode == 0:
        rows = _parse_opencli_json(result.stdout)
    return OpenCLIResult(
        ok=result.returncode == 0,
        rows=rows,
        stdout=result.stdout or "",
        stderr=result.stderr or "",
        returncode=result.returncode,
    )


def run_opencli_sequence(
    commands: Sequence[Sequence[str]],
    runner: Runner = subprocess.run,
    timeout: int = 180,
) -> OpenCLIResult:
    stdout_parts: List[str] = []
    stderr_parts: List[str] = []
    last_stdout = ""
    last_code = 0
    for command in commands:
        result = runner(list(command), check=False, capture_output=True, text=True, timeout=timeout)
        stdout_parts.append(result.stdout or "")
        stderr_parts.append(result.stderr or "")
        last_stdout = result.stdout or ""
        last_code = result.returncode
        if result.returncode != 0:
            return OpenCLIResult(
                ok=False,
                rows=[],
                stdout="\n".join(stdout_parts),
                stderr="\n".join(stderr_parts),
                returncode=result.returncode,
            )
    return OpenCLIResult(
        ok=True,
        rows=_parse_opencli_json(last_stdout),
        stdout="\n".join(stdout_parts),
        stderr="\n".join(stderr_parts),
        returncode=last_code,
    )


def run_opencli_doctor(runner: Runner = subprocess.run) -> OpenCLIResult:
    result = runner(["opencli", "doctor"], check=False, capture_output=True, text=True, timeout=60)
    output = f"{result.stdout or ''}\n{result.stderr or ''}"
    ok = result.returncode == 0 and "Everything looks good" in output
    return OpenCLIResult(ok=ok, rows=[], stdout=result.stdout or "", stderr=result.stderr or "", returncode=result.returncode)


def command_for_task(platform: str, query: str, limit: int) -> List[str]:
    if platform == "xiaohongshu":
        return [
            "opencli",
            "xiaohongshu",
            "search",
            query,
            "--limit",
            str(limit),
            "--trace",
            "on",
            "--keep-tab",
            "true",
            "--window",
            "foreground",
            "-f",
            "json",
        ]
    if platform == "douyin":
        return [
            "opencli",
            "browser",
            DOUYIN_BROWSER_SESSION,
            "--window",
            "foreground",
            "open",
            DOUYIN_JINGXUAN_URL,
        ]
    raise ValueError(f"Unsupported OpenCLI platform: {platform}")


def commands_for_task(
    platform: str,
    query: str,
    limit: int,
    freshness_window_hours: int = 24,
    scroll_rounds: int = 8,
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
    if platform != "douyin":
        return [command_for_task(platform, query, limit)]
    return [
        command_for_task(platform, query, limit),
        ["opencli", "browser", DOUYIN_BROWSER_SESSION, "wait", "time", "3"],
        ["opencli", "browser", DOUYIN_BROWSER_SESSION, "fill", 'input[placeholder*="搜索"]', query],
        ["opencli", "browser", DOUYIN_BROWSER_SESSION, "keys", "Enter"],
        ["opencli", "browser", DOUYIN_BROWSER_SESSION, "wait", "time", "5"],
        ["opencli", "browser", DOUYIN_BROWSER_SESSION, "eval", _apply_recent_filter_js("douyin")],
        ["opencli", "browser", DOUYIN_BROWSER_SESSION, "wait", "time", "2"],
        ["opencli", "browser", DOUYIN_BROWSER_SESSION, "eval", _search_extract_js("douyin", query, limit, freshness_window_hours, scroll_rounds)],
    ]


def normalize_opencli_items(platform: str, command: str, query: str, rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    items = []
    for row in rows:
        if platform == "xiaohongshu" and command == "search":
            item = _normalize_xiaohongshu_search(query, row)
        elif platform == "douyin" and command == "jingxuan_search":
            item = _normalize_douyin_jingxuan_search(query, row)
        elif platform == "douyin" and command == "hashtag":
            item = _normalize_douyin_hashtag(query, row)
        elif platform == "douyin" and command == "location":
            item = _normalize_douyin_location(query, row)
        else:
            item = _normalize_generic(platform, command, query, row)
        item.update(_freshness_fields(row))
        item.update(classify_quality(item))
        if item.get("freshness_status") == "stale":
            item.update({"quality_status": "rejected", "reject_reason": _append_reason(item.get("reject_reason"), "outside_freshness_window")})
        items.append(item)
    return items


def map_opencli_error(message: str) -> str:
    text = message.lower()
    if "authrequired" in text or "login" in text or "登录" in text:
        return "auth_required"
    if "security_block" in text or "security block" in text or "安全限制" in text:
        return "security_block"
    if "emptyresult" in text or "no rows" in text or "empty result" in text:
        return "empty_result"
    return "command_failed"


def run_opencli_rotation(
    config_path: str | Path = "config/live_collect.json",
    output_dir: str | Path = str(opencli_live_output_dir()),
    log_dir: str | Path = str(opencli_live_log_dir()),
    dry_run: bool = False,
    sleep_enabled: bool = True,
    runner: Runner = subprocess.run,
    doctor_result: OpenCLIResult | None = None,
    stage: str = "all",
) -> Dict[str, Any]:
    config = load_live_collect_config(config_path)
    plan = build_rotation_plan(config)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if dry_run:
        return {"ok": True, "event": "opencli_rotate_plan", "run_id": run_id, "dry_run": True, "stage": stage, "tasks": plan}

    doctor = doctor_result or run_opencli_doctor(runner=runner)
    if not doctor.ok:
        return {
            "ok": False,
            "error": "opencli_doctor_failed",
            "message": (doctor.stdout + "\n" + doctor.stderr).strip(),
        }

    output_path = Path(output_dir)
    log_path = Path(log_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    log_path.mkdir(parents=True, exist_ok=True)

    tasks = []
    collected_count = 0
    title_items: List[Dict[str, Any]] = []
    for task in plan:
        platform = task["platform"]
        query = task["query"]
        command_name = "search" if platform == "xiaohongshu" else "jingxuan_search"
        commands = commands_for_task(
            platform,
            query,
            limit=config.max_items_per_task,
            freshness_window_hours=config.freshness_window_hours,
            scroll_rounds=config.scroll_rounds_per_query,
        )
        result = run_opencli_command(commands[0], runner=runner) if len(commands) == 1 else run_opencli_sequence(commands, runner=runner)
        task_file = output_path / f"{run_id}_{platform}_{task['task_index']:04d}.json"
        log_file = log_path / f"{run_id}_{platform}_{task['task_index']:04d}.log"
        log_file.write_text((result.stdout + "\n" + result.stderr).strip(), encoding="utf-8")
        if result.ok:
            items = normalize_opencli_items(platform, command_name, query, result.rows)
            task_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
            collected_count += len([item for item in items if item.get("quality_status") == "accepted"])
            title_items.extend(items)
            tasks.append({"task": task, "ok": True, "stored": len(items), "output": str(task_file), "log": str(log_file)})
        else:
            tasks.append(
                {
                    "task": task,
                    "ok": False,
                    "error": map_opencli_error(result.stderr or result.stdout),
                    "log": str(log_file),
                }
            )
        if sleep_enabled:
            time.sleep(int(task["wait_after_seconds"]))

    screened_items: List[Dict[str, Any]] = []
    video_results: List[Dict[str, Any]] = []
    title_pool_file = output_path / f"{run_id}_title_pool.json"
    title_pool_file.write_text(json.dumps(title_items, ensure_ascii=False, indent=2), encoding="utf-8")
    if stage in {"screen", "videos", "all"}:
        screened_items = screen_title_pool(title_items, per_platform_limit=config.deep_process_limit_per_platform)
        screened_file = output_path / f"{run_id}_screened.json"
        screened_file.write_text(json.dumps(screened_items, ensure_ascii=False, indent=2), encoding="utf-8")
    if stage in {"videos", "all"}:
        media_root = opencli_media_dir(run_id)
        asr_config = ASRConfig(
            backend=config.asr_backend,
            model=config.asr_model,
            language=config.asr_language,
            enable_keyframes=config.enable_keyframes,
        )
        for item in screened_items:
            video_results.append(process_video_item(item, media_root, config=asr_config, runner=runner))
        video_file = output_path / f"{run_id}_video_asr_results.json"
        video_file.write_text(json.dumps(video_results, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "ok": True,
        "event": "opencli_rotate_done",
        "run_id": run_id,
        "stage": stage,
        "collected": collected_count,
        "title_pool": str(title_pool_file),
        "screened_count": len(screened_items),
        "video_results_count": len(video_results),
        "tasks": tasks,
    }
    summary_file = log_path / f"hermes_collect_opencli_{run_id}.summary.json"
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["summary"] = str(summary_file)
    return summary


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


def _normalize_xiaohongshu_search(query: str, row: Mapping[str, Any]) -> Dict[str, Any]:
    title = _clean(row.get("title"))
    author = _clean(row.get("author"))
    return {
        "title": title,
        "body": f"小红书搜索结果：{title}。作者：{author}。关键词：{query}",
        "source": "opencli xiaohongshu search",
        "platform": "xiaohongshu",
        "url": _clean(row.get("url")),
        "published_at": _clean(row.get("published_at")),
        "published_at_raw": _clean(row.get("published_at_raw") or row.get("published_at")),
        "author": author,
        "content_type": "mixed",
        "engagement": {"likes": _to_int(row.get("likes")), "comments": 0, "shares": 0, "collects": 0},
        "comments": [],
        "query": query,
        "capture_method": "opencli_browser_bridge",
        "evidence": {"opencli_command": "xiaohongshu browser search + freshness filter + scroll", "trace": "opencli browser", "source_page": _clean(row.get("source_page"))},
    }


def _normalize_douyin_hashtag(query: str, row: Mapping[str, Any]) -> Dict[str, Any]:
    name = _clean(row.get("name"))
    return {
        "title": name,
        "body": f"抖音话题信号：{name}",
        "source": "opencli douyin hashtag",
        "platform": "douyin",
        "url": "",
        "published_at": "",
        "author": "",
        "content_type": "topic",
        "signal_type": "hashtag",
        "engagement": {"views": _to_int(row.get("view_count")), "likes": 0, "comments": 0, "shares": 0, "collects": 0},
        "comments": [],
        "query": query,
        "capture_method": "opencli_browser_bridge",
        "evidence": {"opencli_command": "douyin hashtag search", "trace": "opencli --trace on", "external_id": _clean(row.get("id"))},
    }


def _normalize_douyin_jingxuan_search(query: str, row: Mapping[str, Any]) -> Dict[str, Any]:
    title = _clean(row.get("title") or row.get("text"))
    body = _clean(row.get("body") or row.get("text"))
    return {
        "title": title,
        "body": body or f"抖音精选页入口搜索结果。关键词：{query}",
        "source": "opencli douyin jingxuan search",
        "platform": "douyin",
        "url": _clean(row.get("url") or DOUYIN_JINGXUAN_URL),
        "published_at": _clean(row.get("published_at")),
        "published_at_raw": _clean(row.get("published_at_raw")),
        "author": _clean(row.get("author")),
        "content_type": "video",
        "signal_type": "search_result_visible",
        "engagement": {"likes": _to_int(row.get("likes")), "comments": 0, "shares": 0, "collects": 0},
        "comments": [],
        "query": query,
        "capture_method": "opencli_browser_bridge",
        "evidence": {
            "opencli_command": "browser open douyin jingxuan + fill search query + eval search results",
            "entry_url": DOUYIN_JINGXUAN_URL,
            "search_query": query,
            "source_page": _clean(row.get("source_page")),
        },
    }


def _normalize_douyin_location(query: str, row: Mapping[str, Any]) -> Dict[str, Any]:
    name = _clean(row.get("name"))
    return {
        "title": name,
        "body": _clean(row.get("address")),
        "source": "opencli douyin location",
        "platform": "douyin",
        "url": "",
        "published_at": "",
        "author": "",
        "content_type": "poi",
        "signal_type": "location",
        "engagement": {"likes": 0, "comments": 0, "shares": 0, "collects": 0},
        "comments": [],
        "query": query,
        "capture_method": "opencli_browser_bridge",
        "evidence": {"opencli_command": "douyin location", "external_id": _clean(row.get("poi_id"))},
    }


def _normalize_generic(platform: str, command: str, query: str, row: Mapping[str, Any]) -> Dict[str, Any]:
    title = _clean(row.get("title") or row.get("name") or row.get("id"))
    return {
        "title": title,
        "body": json.dumps(row, ensure_ascii=False),
        "source": f"opencli {platform} {command}",
        "platform": platform,
        "url": _clean(row.get("url")),
        "published_at": _clean(row.get("published_at") or row.get("create_time")),
        "author": _clean(row.get("author")),
        "content_type": "unknown",
        "engagement": {"likes": _to_int(row.get("likes") or row.get("digg_count")), "comments": 0, "shares": 0, "collects": 0},
        "comments": [],
        "query": query,
        "capture_method": "opencli_browser_bridge",
        "evidence": {"opencli_command": f"{platform} {command}"},
    }


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


def screen_title_pool(items: Sequence[Mapping[str, Any]], per_platform_limit: int = 40) -> List[Dict[str, Any]]:
    accepted = [dict(item) for item in items if item.get("quality_status") == "accepted"]
    hermes_rows = _screen_with_hermes(accepted, per_platform_limit)
    if hermes_rows:
        return hermes_rows
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for item in accepted:
        platform = str(item.get("platform") or "unknown")
        item["deep_process_status"] = "selected_for_asr"
        item["decision_hints"] = _decision_hints(item)
        item["screen_score"] = _screen_score(item)
        buckets.setdefault(platform, []).append(item)
    result: List[Dict[str, Any]] = []
    for platform_items in buckets.values():
        result.extend(sorted(platform_items, key=lambda row: row.get("screen_score", 0), reverse=True)[:per_platform_limit])
    return result


def _screen_with_hermes(items: Sequence[Mapping[str, Any]], per_platform_limit: int) -> List[Dict[str, Any]]:
    if os.getenv("AETHERFLUX_HERMES_SCREEN", "0").lower() not in {"1", "true", "yes"}:
        return []
    if not shutil.which("hermes"):
        return []
    brief = [
        {
            "id": _clean(item.get("platform_item_id") or item.get("url") or item.get("title")),
            "platform": item.get("platform", ""),
            "title": item.get("title", ""),
            "body": str(item.get("body", ""))[:240],
            "url": item.get("url", ""),
            "published_at_raw": item.get("published_at_raw", ""),
            "engagement": item.get("engagement", {}),
            "freshness_status": item.get("freshness_status", ""),
        }
        for item in items[:500]
    ]
    task = (
        "你是 AetherFlux V0.2.3 标题池初筛 agent。"
        "请只输出 JSON 数组，不要解释。"
        "从候选中按机会+风险优先筛选需要 ASR 深处理的视频。"
        f"每个平台最多 {per_platform_limit} 条。"
        "每条输出 id, deep_process, priority_score, category, reasons。"
        f"\n候选 JSON:\n{json.dumps(brief, ensure_ascii=False)}"
    )
    try:
        result = subprocess.run(
            ["hermes", "-z", task, "--provider", "deepseek", "--model", "deepseek-v4-pro"],
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        import sys
        print('[AetherFlux] WARNING: Hermes screen timed out', file=sys.stderr)
        return []
    except FileNotFoundError:
        print('[AetherFlux] WARNING: Hermes CLI not found', file=sys.stderr)
        return []
    except Exception as exc:
        print(f'[AetherFlux] WARNING: Hermes screen failed: {exc}', file=sys.stderr)
        return []
    if result.returncode != 0:
        return []
    decisions = _extract_json_array(result.stdout)
    if not decisions:
        return []
    decision_by_id = {str(row.get("id")): row for row in decisions if isinstance(row, Mapping) and row.get("deep_process")}
    selected: List[Dict[str, Any]] = []
    for item in items:
        item_id = _clean(item.get("platform_item_id") or item.get("url") or item.get("title"))
        decision = decision_by_id.get(item_id)
        if not decision:
            continue
        enriched = dict(item)
        enriched.update(
            {
                "deep_process_status": "selected_for_asr",
                "decision_hints": decision.get("reasons") or _decision_hints(item),
                "screen_score": int(decision.get("priority_score") or _screen_score(item)),
                "screen_source": "hermes",
                "screen_category": decision.get("category", ""),
            }
        )
        selected.append(enriched)
    return selected


def _extract_json_array(text: str) -> List[Dict[str, Any]]:
    stripped = text.strip()
    candidates = [stripped]
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start >= 0 and end > start:
        candidates.append(stripped[start : end + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            return [dict(row) for row in data if isinstance(row, Mapping)]
    return []


def _screen_score(item: Mapping[str, Any]) -> int:
    text = f"{item.get('title') or ''} {item.get('body') or ''}"
    score = int(item.get("quality_score") or 0)
    score += min(40, int(((item.get("engagement") or {}).get("likes") or 0) / 1000))
    score += 20 * len(_decision_hints(item))
    if item.get("freshness_status") == "recent":
        score += 20
    return score


def _decision_hints(item: Mapping[str, Any]) -> List[str]:
    text = f"{item.get('title') or ''} {item.get('body') or ''}"
    hints = []
    if any(term in text for term in ("避雷", "投诉", "宰客", "排队", "堵车", "坑", "贵")):
        hints.append("risk")
    if any(term in text for term in ("攻略", "路线", "玩法", "体验", "推荐", "小众", "民宿", "旅拍")):
        hints.append("opportunity")
    return hints or ["general"]


def _freshness_fields(row: Mapping[str, Any]) -> Dict[str, Any]:
    raw = _clean(row.get("published_at_raw") or row.get("published_at"))
    window_hours = _to_int(row.get("freshness_window_hours")) or 24
    freshness = evaluate_freshness(raw, window_hours=window_hours)
    return {
        "published_at_raw": raw,
        "published_at": freshness.published_at,
        "freshness_status": freshness.status,
        "freshness_window_hours": window_hours,
        "ui_filter_applied": bool(row.get("ui_filter_applied")),
        "freshness_reason": freshness.reason,
    }


def _append_reason(existing: Any, reason: str) -> str:
    text = str(existing or "").strip()
    return ",".join([part for part in [text, reason] if part])


def _apply_recent_filter_js(platform: str) -> str:
    platform_json = json.dumps(platform)
    return f"""
(() => {{
  const platform = {platform_json};
  const labels = platform === "xiaohongshu"
    ? ["最新", "一天内", "24小时内", "当天", "今天"]
    : ["筛选", "最新发布", "一天内", "24小时内", "今天"];
  let clicked = false;
  for (const label of labels) {{
    const nodes = Array.from(document.querySelectorAll("button, div, span, a")).filter((node) => (node.innerText || node.textContent || "").trim() === label);
    for (const node of nodes.slice(0, 2)) {{
      try {{
        node.click();
        clicked = true;
      }} catch (_err) {{}}
    }}
  }}
  window.__aetherflux_recent_filter_applied = clicked;
  return JSON.stringify([{{ platform, ui_filter_applied: clicked, source_page: location.href }}]);
}})()
""".strip()


def _search_extract_js(platform: str, query: str, limit: int, freshness_window_hours: int, scroll_rounds: int) -> str:
    platform_json = json.dumps(platform)
    query_json = json.dumps(query, ensure_ascii=False)
    limit_json = json.dumps(limit)
    window_json = json.dumps(freshness_window_hours)
    scroll_json = json.dumps(scroll_rounds)
    return f"""
(async () => {{
  const platform = {platform_json};
  const query = {query_json};
  const maxRows = {limit_json};
  const freshnessWindowHours = {window_json};
  const scrollRounds = {scroll_json};
  const seen = new Set();
  const rows = [];

  const normalizeText = (value) => (value || "").replace(/\\s+/g, " ").trim();
  const pickTitle = (card) => {{
    const imgAlt = card.querySelector("img[alt]")?.getAttribute("alt") || "";
    if (imgAlt.trim()) return normalizeText(imgAlt);
    const lines = (card.innerText || "")
      .split("\\n")
      .map((line) => normalizeText(line))
      .filter(Boolean)
      .filter((line) => !/^\\d{{1,2}}:\\d{{2}}$/.test(line))
      .filter((line) => !/^\\d+(\\.\\d+)?万?$/.test(line))
      .filter((line) => !line.startsWith("@"))
      .filter((line) => !line.startsWith("·"));
    return lines.sort((a, b) => b.length - a.length)[0] || "";
  }};

  const extractOnce = (round) => {{
  const selector = platform === "xiaohongshu"
    ? 'a[href*="/explore/"], a[href*="/search_result/"], section, div[class*="note"], div[class*="card"]'
    : '[id^="waterfall_item_"], div[href^="/video/"], a[href*="/video/"]';
  const cards = Array.from(document.querySelectorAll(selector));
  for (const card of cards) {{
    const text = normalizeText(card.innerText || card.textContent || "");
    if (!text || text.includes("相关搜索")) continue;
    const href = card.getAttribute("href") || card.querySelector('a[href], [href^="/video/"], a[href*="/video/"]')?.getAttribute("href") || "";
    const rawId = (card.id || "").replace(/^waterfall_item_/, "");
    const url = href
      ? new URL(href, location.origin).href
      : (/^\\d+$/.test(rawId) ? `${{location.origin}}/video/${{rawId}}` : "");
    if (!url || seen.has(url)) continue;
    seen.add(url);
    const title = pickTitle(card) || document.title || "抖音搜索结果视频";
    const authorMatch = (card.innerText || "").match(/@\\s*([^\\n·]+)/);
    const likesMatch = text.match(/(?:^|\\s)(\\d+(?:\\.\\d+)?万?)(?=\\s|$)/);
    const timeMatch = text.match(/(刚刚|刚才|\\d+\\s*分钟前|\\d+\\s*小时前|今天\\s*\\d{{1,2}}:\\d{{2}}|昨天\\s*\\d{{1,2}}:\\d{{2}}|\\d{{4}}年\\d{{1,2}}月\\d{{1,2}}日?|\\d{{1,2}}月\\d{{1,2}}日?)/);
    rows.push({{
      title: title.slice(0, 120),
      body: text || title || `抖音搜索结果可见内容。关键词：${{query}}`,
      url,
      author: authorMatch ? authorMatch[1].trim() : "",
      likes: likesMatch ? likesMatch[1] : "",
      platform_item_id: rawId || url.split("/").filter(Boolean).pop() || "",
      published_at_raw: timeMatch ? timeMatch[1] : "",
      ui_filter_applied: Boolean(window.__aetherflux_recent_filter_applied),
      freshness_window_hours: freshnessWindowHours,
      scroll_round: round,
      source_page: location.href,
      captured_at: new Date().toISOString()
    }});
    if (rows.length >= maxRows) break;
  }}
  }};
  for (let round = 0; round <= scrollRounds; round += 1) {{
    extractOnce(round);
    if (rows.length >= maxRows) break;
    window.scrollBy(0, Math.max(600, window.innerHeight * 0.85));
    await new Promise((resolve) => setTimeout(resolve, 900));
  }}
  if (!rows.length) {{
    rows.push({{
      title: document.title || "抖音搜索结果页",
      body: (document.body && document.body.innerText || "").replace(/\\s+/g, " ").trim().slice(0, 500),
      url: location.href,
      author: "",
      published_at_raw: "",
      ui_filter_applied: Boolean(window.__aetherflux_recent_filter_applied),
      freshness_window_hours: freshnessWindowHours,
      scroll_round: 0,
      source_page: location.href,
      captured_at: new Date().toISOString()
    }});
  }}
  return JSON.stringify(rows);
}})()
""".strip()
