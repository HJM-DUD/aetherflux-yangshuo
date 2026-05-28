"""Xiaohongshu collection policy for Yangshuo tourism intelligence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, time, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol


ASIA_SHANGHAI = timezone(timedelta(hours=8))

DEFAULT_QUERY_CLUSTERS: List[Dict[str, Any]] = [
    {"id": "scenic_routes", "label": "景点/线路", "queries": ["阳朔 攻略", "阳朔 路线", "阳朔 兴坪 漓江", "阳朔 十里画廊"]},
    {"id": "bamboo_rafting", "label": "竹筏/水上", "queries": ["阳朔 遇龙河 竹筏", "阳朔 漓江 竹筏", "阳朔 竹筏 排队"]},
    {"id": "cycling_hiking", "label": "骑行/徒步", "queries": ["阳朔 骑行", "阳朔 徒步", "阳朔 十里画廊 骑行"]},
    {"id": "hotels_homestays", "label": "住宿民宿", "queries": ["阳朔 民宿", "阳朔 酒店", "阳朔 西街 住宿"]},
    {"id": "food_nightlife", "label": "餐饮夜生活", "queries": ["阳朔 美食", "阳朔 西街 夜生活", "阳朔 咖啡"]},
    {"id": "family_couples", "label": "亲子情侣", "queries": ["阳朔 亲子", "阳朔 情侣", "阳朔 带娃"]},
    {"id": "photo_shooting", "label": "旅拍摄影", "queries": ["阳朔 旅拍", "阳朔 拍照", "阳朔 相公山 日出"]},
    {"id": "rain_traffic", "label": "雨季交通", "queries": ["阳朔 天气", "阳朔 暴雨", "阳朔 停车", "阳朔 堵车"]},
    {"id": "complaints_risks", "label": "避雷投诉", "queries": ["阳朔 避雷", "阳朔 投诉", "阳朔 宰客", "阳朔 排队"]},
    {"id": "foreign_view", "label": "外语游客视角", "queries": ["Yangshuo 小红书", "Yangshuo travel", "外国人 阳朔"]},
]


class XHSDriver(Protocol):
    def search(self, query: str, cluster_id: str) -> Iterable[Mapping[str, Any]]:
        """Return raw notes visible for a query."""


@dataclass
class XHSState:
    last_success_at: str = ""
    watermark_published_at: str = ""
    last_query_clusters: List[str] = field(default_factory=list)
    last_error: str = ""

    @classmethod
    def load(cls, path: Path | str) -> "XHSState":
        target = Path(path)
        if not target.exists():
            return cls()
        payload = json.loads(target.read_text(encoding="utf-8"))
        return cls(
            last_success_at=str(payload.get("last_success_at", "")),
            watermark_published_at=str(payload.get("watermark_published_at", "")),
            last_query_clusters=list(payload.get("last_query_clusters", [])),
            last_error=str(payload.get("last_error", "")),
        )

    def save(self, path: Path | str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "last_success_at": self.last_success_at,
                    "watermark_published_at": self.watermark_published_at,
                    "last_query_clusters": self.last_query_clusters,
                    "last_error": self.last_error,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


class JSONFeedXHSDriver:
    """Deterministic driver used by tests and by CLI dry runs."""

    def __init__(self, source_path: Path | str) -> None:
        self.source_path = Path(source_path)

    def search(self, query: str, cluster_id: str) -> Iterable[Mapping[str, Any]]:
        if not self.source_path.exists():
            return []
        items = json.loads(self.source_path.read_text(encoding="utf-8"))
        matched = []
        for item in items:
            item_query = item.get("query")
            item_queries = item.get("queries", [])
            item_cluster = item.get("cluster_id")
            if item_query == query or query in item_queries or item_cluster == cluster_id:
                matched.append(item)
        return matched


def collect_xhs(
    driver: XHSDriver,
    mode: str,
    state_path: Path | str,
    output_path: Path | str,
    days: int = 7,
    now: Optional[datetime] = None,
    clusters: Optional[Iterable[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    current_time = _as_utc(now or datetime.now(timezone.utc))
    state = XHSState.load(state_path)
    query_clusters = list(clusters or DEFAULT_QUERY_CLUSTERS)
    start_at = _start_at_for(mode, days, current_time)
    watermark = state.watermark_published_at if mode == "daily" else None

    try:
        collected: List[Dict[str, Any]] = []
        executed_clusters: List[str] = []
        for cluster in query_clusters:
            cluster_id = str(cluster["id"])
            executed_clusters.append(cluster_id)
            for query in cluster.get("queries", []):
                for item in driver.search(str(query), cluster_id):
                    collected.append(normalize_raw_item(item, str(query), cluster_id, current_time))
        unique_collected = dedupe_raw_items(collected)
        filtered = filter_by_window(unique_collected, start_at=start_at, watermark=watermark)
        deduped = dedupe_raw_items(filtered)
        _write_items(output_path, deduped)

        state.last_success_at = _format_utc(current_time)
        state.watermark_published_at = _latest_published_at(deduped) or state.watermark_published_at
        state.last_query_clusters = executed_clusters
        state.last_error = ""
        state.save(state_path)
        return {
            "mode": mode,
            "raw": len(unique_collected),
            "stored": len(deduped),
            "duplicates_merged": max(0, len(filtered) - len(deduped)),
            "output": str(output_path),
            "state": str(state_path),
            "watermark_published_at": state.watermark_published_at,
        }
    except Exception as exc:
        state.last_error = str(exc)
        state.save(state_path)
        raise


def normalize_raw_item(item: Mapping[str, Any], query: str, cluster_id: str, fetched_at: datetime) -> Dict[str, Any]:
    return {
        "title": _clean(item.get("title")) or "未命名小红书笔记",
        "body": _clean(item.get("body")),
        "source": _clean(item.get("source")) or "小红书搜索",
        "platform": "xiaohongshu",
        "url": _clean(item.get("url")),
        "published_at": _format_utc(_parse_datetime(item.get("published_at")) or fetched_at),
        "author": _clean(item.get("author")),
        "engagement": _normalize_engagement(item.get("engagement", {})),
        "query": query,
        "cluster_id": cluster_id,
        "fetched_at": _format_utc(fetched_at),
        "snapshot_ref": _clean(item.get("snapshot_ref")),
    }


def filter_by_window(
    items: Iterable[Mapping[str, Any]],
    start_at: Optional[datetime],
    watermark: Optional[str],
) -> List[Dict[str, Any]]:
    watermark_dt = _parse_datetime(watermark) if watermark else None
    kept: List[Dict[str, Any]] = []
    for item in items:
        published_at = _parse_datetime(item.get("published_at"))
        if published_at is None:
            continue
        if start_at is not None and published_at < _as_utc(start_at):
            continue
        if watermark_dt is not None and published_at <= watermark_dt:
            continue
        kept.append(dict(item))
    return kept


def dedupe_raw_items(items: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for item in items:
        key = _dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(item))
    return deduped


def parse_now(value: str) -> datetime:
    parsed = _parse_datetime(value)
    if parsed is None:
        raise ValueError(f"Invalid datetime: {value}")
    return parsed


def _start_at_for(mode: str, days: int, now: datetime) -> Optional[datetime]:
    if mode == "backfill":
        return now - timedelta(days=days)
    if mode == "daily":
        local_now = _as_utc(now).astimezone(ASIA_SHANGHAI)
        local_start = datetime.combine(local_now.date(), time.min, tzinfo=ASIA_SHANGHAI)
        return local_start.astimezone(timezone.utc)
    raise ValueError(f"Unsupported XHS collection mode: {mode}")


def _write_items(path: Path | str, items: Iterable[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(list(items), ensure_ascii=False, indent=2), encoding="utf-8")


def _latest_published_at(items: Iterable[Mapping[str, Any]]) -> str:
    dates = [_parse_datetime(item.get("published_at")) for item in items]
    valid_dates = [date for date in dates if date is not None]
    if not valid_dates:
        return ""
    return _format_utc(max(valid_dates))


def _dedupe_key(item: Mapping[str, Any]) -> str:
    url = _clean(item.get("url"))
    if url:
        return f"url:{url.split('?')[0]}"
    text = f"{_clean(item.get('title'))}|{_clean(item.get('body'))[:160]}"
    return "content:" + hashlib.sha1(text.encode("utf-8")).hexdigest()


def _normalize_engagement(value: Any) -> Dict[str, int]:
    if not isinstance(value, Mapping):
        return {"likes": 0, "comments": 0, "shares": 0}
    return {
        "likes": _to_int(value.get("likes")),
        "comments": _to_int(value.get("comments")),
        "shares": _to_int(value.get("shares")),
    }


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = datetime.combine(value.date(), time(value.hour, value.minute, value.second), tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _format_utc(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
