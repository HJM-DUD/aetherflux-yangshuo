"""Platform support policy for V0.2.5 shellCLI collection."""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple


SUPPORTED_PLATFORMS = {"xiaohongshu", "douyin"}
DISABLED_PLACEHOLDERS = {"shipinghao"}


def plan_supported_tasks(platforms: Iterable[str], queries: Iterable[str], per_platform: int = 1) -> Tuple[List[Dict[str, object]], List[Dict[str, str]]]:
    tasks: List[Dict[str, object]] = []
    errors: List[Dict[str, str]] = []
    query_list = [query for query in queries if str(query).strip()]
    for platform in platforms:
        if platform in SUPPORTED_PLATFORMS:
            for index, query in enumerate(query_list[:per_platform], start=1):
                tasks.append({"platform": platform, "query": query, "task_index": len(tasks) + 1})
        elif platform in DISABLED_PLACEHOLDERS:
            errors.append({"platform": platform, "status": "disabled_unsupported_v025", "message": "视频号在 V0.2.5 只保留占位，不进入真实采集队列。"})
        else:
            errors.append({"platform": platform, "status": "unsupported_platform", "message": "平台未接入。"})
    return tasks, errors
