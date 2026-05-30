"""Adaptive slow rotation for logged-in live collection."""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping

from .live_collectors import BrowserConnectionError, collect_live_platform
from .query_planner import build_hybrid_queries
from .paths import live_rotate_log_dir, live_rotate_output_dir
from .quality import classify_quality


DEFAULT_CONFIG = Path("config/live_collect.json")


@dataclass
class PlatformHealth:
    platform: str
    consecutive_failures: int = 0
    rejected_recent: int = 0
    accepted_recent: int = 0
    paused: bool = False
    cooldown_minutes: int = 0


@dataclass
class LiveCollectConfig:
    platforms: List[str]
    queries: List[str]
    target_per_platform: int = 20
    wait_min_seconds: int = 90
    wait_max_seconds: int = 240
    max_items_per_task: int = 1
    detail_limit_per_task: int = 1
    freshness_window_hours: int = 24
    title_target_per_platform: int = 200
    deep_process_limit_per_platform: int = 40
    scroll_rounds_per_query: int = 8
    scroll_stop_after_no_new_rounds: int = 2
    query_strategy: str = "hybrid"
    video_processing_priority: str = "asr"
    enable_keyframes: bool = False
    asr_backend: str = "auto"
    asr_model: str = "small"
    asr_language: str = "zh"
    health: Dict[str, PlatformHealth] = field(default_factory=dict)


def load_live_collect_config(path: str | Path = DEFAULT_CONFIG) -> LiveCollectConfig:
    config_path = Path(path)
    raw: Dict[str, Any] = {}
    if config_path.exists():
        raw = json.loads(config_path.read_text(encoding="utf-8"))

    platforms = _split_env_list(os.getenv("AETHERFLUX_LIVE_PLATFORMS"), ",") or list(raw.get("platforms", []))
    queries = _split_env_list(os.getenv("AETHERFLUX_LIVE_QUERIES"), ";") or list(raw.get("queries", []))
    if not platforms:
        platforms = ["xiaohongshu", "douyin"]
    if not queries:
        queries = ["阳朔 旅游", "阳朔 竹筏", "阳朔 西街"]
    if raw.get("query_strategy", "manual") == "hybrid" and not os.getenv("AETHERFLUX_LIVE_QUERIES"):
        queries = [item.query for item in build_hybrid_queries(raw)]

    return LiveCollectConfig(
        platforms=platforms,
        queries=queries,
        target_per_platform=int(os.getenv("AETHERFLUX_TARGET_PER_PLATFORM", raw.get("target_per_platform", 20))),
        wait_min_seconds=int(os.getenv("AETHERFLUX_WAIT_MIN_SECONDS", raw.get("wait_min_seconds", 90))),
        wait_max_seconds=int(os.getenv("AETHERFLUX_WAIT_MAX_SECONDS", raw.get("wait_max_seconds", 240))),
        max_items_per_task=int(os.getenv("AETHERFLUX_MAX_ITEMS_PER_TASK", raw.get("max_items_per_task", 1))),
        detail_limit_per_task=int(os.getenv("AETHERFLUX_DETAIL_LIMIT_PER_TASK", raw.get("detail_limit_per_task", 1))),
        freshness_window_hours=int(os.getenv("AETHERFLUX_FRESHNESS_WINDOW_HOURS", raw.get("freshness_window_hours", 24))),
        title_target_per_platform=int(os.getenv("AETHERFLUX_TITLE_TARGET_PER_PLATFORM", raw.get("title_target_per_platform", 200))),
        deep_process_limit_per_platform=int(os.getenv("AETHERFLUX_DEEP_PROCESS_LIMIT_PER_PLATFORM", raw.get("deep_process_limit_per_platform", 40))),
        scroll_rounds_per_query=int(os.getenv("AETHERFLUX_SCROLL_ROUNDS_PER_QUERY", raw.get("scroll_rounds_per_query", 8))),
        scroll_stop_after_no_new_rounds=int(os.getenv("AETHERFLUX_SCROLL_STOP_AFTER_NO_NEW_ROUNDS", raw.get("scroll_stop_after_no_new_rounds", 2))),
        query_strategy=str(os.getenv("AETHERFLUX_QUERY_STRATEGY", raw.get("query_strategy", "manual"))),
        video_processing_priority=str(os.getenv("AETHERFLUX_VIDEO_PROCESSING_PRIORITY", raw.get("video_processing_priority", "asr"))),
        enable_keyframes=str(os.getenv("AETHERFLUX_ENABLE_KEYFRAMES", raw.get("enable_keyframes", False))).lower() in {"1", "true", "yes"},
        asr_backend=str(os.getenv("AETHERFLUX_ASR_BACKEND", raw.get("asr_backend", "auto"))),
        asr_model=str(os.getenv("AETHERFLUX_ASR_MODEL", raw.get("asr_model", "small"))),
        asr_language=str(os.getenv("AETHERFLUX_ASR_LANGUAGE", raw.get("asr_language", "zh"))),
    )


def build_rotation_plan(config: LiveCollectConfig, rng: random.Random | None = None) -> List[Dict[str, Any]]:
    generator = rng or random.SystemRandom()
    active_platforms = [platform for platform in config.platforms if not config.health.get(platform, PlatformHealth(platform)).paused]
    plan: List[Dict[str, Any]] = []
    offsets: Dict[tuple[str, str], int] = {}
    if not active_platforms or not config.queries:
        return plan

    for index in range(config.target_per_platform):
        query = config.queries[index % len(config.queries)]
        for platform in active_platforms:
            offset_key = (platform, query)
            item_offset = offsets.get(offset_key, 0)
            offsets[offset_key] = item_offset + 1
            plan.append(
                {
                    "platform": platform,
                    "query": query,
                    "task_index": len(plan) + 1,
                    "item_offset": item_offset,
                    "wait_after_seconds": generator.randint(config.wait_min_seconds, config.wait_max_seconds),
                }
            )
    return plan


def hermes_decision(health: Mapping[str, PlatformHealth]) -> Dict[str, Any]:
    bad_platforms = [
        item.platform
        for item in health.values()
        if item.consecutive_failures >= 2 or item.rejected_recent >= 3 or item.paused
    ]
    if bad_platforms and len(bad_platforms) >= len(health):
        return {"action": "stop_and_ask_human", "reason": "all_platforms_unhealthy", "platforms": bad_platforms}
    if bad_platforms:
        return {"action": "pause_platform", "platform": bad_platforms[0], "cooldown_minutes": 60}
    return {"action": "continue", "reason": "platforms_healthy"}


def run_rotation_collection(
    config_path: str | Path = DEFAULT_CONFIG,
    cdp_url: str = "http://127.0.0.1:9222",
    output_dir: str | Path = str(live_rotate_output_dir()),
    log_dir: str | Path = str(live_rotate_log_dir()),
    dry_run: bool = False,
    sleep_enabled: bool = True,
) -> Dict[str, Any]:
    config = load_live_collect_config(config_path)
    plan = build_rotation_plan(config)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = Path(output_dir)
    log_path = Path(log_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    log_path.mkdir(parents=True, exist_ok=True)

    if dry_run:
        return {"ok": True, "event": "live_rotate_plan", "run_id": run_id, "dry_run": True, "tasks": plan}

    health = {platform: PlatformHealth(platform=platform) for platform in config.platforms}
    collected: List[Dict[str, Any]] = []
    task_results: List[Dict[str, Any]] = []
    for task in plan:
        platform = task["platform"]
        query = task["query"]
        if health[platform].paused:
            task_results.append({"task": task, "skipped": True, "reason": "platform_paused"})
            continue
        task_file = output_path / f"{run_id}_{platform}_{task['task_index']:04d}.json"
        try:
            items = collect_live_platform(
                platform,
                query,
                cdp_url=cdp_url,
                max_items=config.max_items_per_task,
                detail_limit=config.detail_limit_per_task,
                skip_items=int(task.get("item_offset", 0)),
            )
            accepted = []
            rejected = []
            for item in items:
                quality = classify_quality(item)
                enriched = {**item, **quality}
                if quality["quality_status"] == "accepted":
                    accepted.append(enriched)
                    collected.append(enriched)
                else:
                    rejected.append(enriched)
            health[platform].consecutive_failures = 0 if accepted else health[platform].consecutive_failures + 1
            health[platform].accepted_recent += len(accepted)
            health[platform].rejected_recent += len(rejected)
            task_file.write_text(json.dumps({"accepted": accepted, "rejected": rejected}, ensure_ascii=False, indent=2), encoding="utf-8")
            task_results.append({"task": task, "accepted": len(accepted), "rejected": len(rejected), "output": str(task_file)})
        except BrowserConnectionError as exc:
            health[platform].consecutive_failures += 1
            task_results.append({"task": task, "error": "browser_connection_failed", "message": str(exc)})
        except Exception as exc:  # pragma: no cover - browser/platform dependent
            health[platform].consecutive_failures += 1
            task_results.append({"task": task, "error": "collection_failed", "message": str(exc)})

        decision = hermes_decision(health)
        if decision["action"] == "stop_and_ask_human":
            break
        if decision["action"] == "pause_platform":
            health[str(decision["platform"])].paused = True
        if sleep_enabled:
            time.sleep(int(task["wait_after_seconds"]))

    summary = {
        "ok": True,
        "event": "live_rotate_done",
        "run_id": run_id,
        "collected": len(collected),
        "tasks": task_results,
        "health": {name: vars(item) for name, item in health.items()},
        "hermes_decision": hermes_decision(health),
    }
    summary_file = log_path / f"hermes_collect_live_{run_id}.summary.json"
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["summary"] = str(summary_file)
    return summary


def _split_env_list(value: str | None, separator: str) -> List[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(separator) if part.strip()]
