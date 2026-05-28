"""V0.2.0 local-first collector primitives."""

from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Mapping
from urllib.parse import urlsplit, urlunsplit


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", re.IGNORECASE)

_PLACE_ALIASES = {
    "yangshuo": ("阳朔", "yangshuo"),
    "wuhan": ("武汉", "wuhan"),
    "palau": ("帕劳", "palau"),
    "遇龙河": ("遇龙河", "yulong"),
    "西街": ("西街", "west street"),
    "兴坪": ("兴坪", "xingping"),
    "十里画廊": ("十里画廊", "ten mile", "ten-mile"),
    "漓江": ("漓江", "li river"),
}

_INTENT_ALIASES = {
    "queue_ticket": ("排队", "票务", "预约", "限流", "ticket", "queue"),
    "price_complaint": ("宰客", "太贵", "价格", "投诉", "overpriced", "scam"),
    "traffic_parking": ("停车", "堵车", "交通", "管制", "parking", "traffic"),
    "route_content": ("路线", "攻略", "骑行", "itinerary", "route", "cycling"),
    "hotel_stay": ("民宿", "酒店", "住宿", "hotel", "homestay"),
    "food": ("餐饮", "美食", "饭店", "food", "restaurant"),
    "wellness": ("疗愈", "康养", "冥想", "wellness", "retreat"),
}


def make_hard_dedupe_key(item: Mapping[str, Any]) -> str:
    """Return a key for truly identical content only."""
    platform = _clean(item.get("platform")).lower() or "unknown"
    content_id = _clean(item.get("content_id") or item.get("platform_item_id"))
    if content_id:
        return f"{platform}:id:{content_id}"
    url = _canonical_url(_clean(item.get("url")))
    if url:
        return f"{platform}:url:{url}"
    media_sha = _clean(item.get("media_sha256") or item.get("video_sha256") or item.get("image_sha256"))
    if media_sha:
        return f"{platform}:media:{media_sha}"
    exact_text = "|".join(
        [
            platform,
            _clean(item.get("author")),
            _clean(item.get("title")),
            _clean(item.get("body") or item.get("description")),
        ]
    )
    return f"{platform}:exact:{_sha1(exact_text)}"


def make_topic_cluster_key(item: Mapping[str, Any]) -> str:
    """Return a topic key. Similar events from different users should share it."""
    text = _clean(" ".join(str(item.get(key, "")) for key in ("mission_place", "title", "body", "description", "transcript"))).lower()
    place = _first_alias(text, _PLACE_ALIASES) or _clean(item.get("mission_place")).lower() or "general"
    intent = _first_alias(text, _INTENT_ALIASES) or _fallback_topic(text)
    return f"{place}:{intent}"


def copy_similarity(first: Mapping[str, Any], second: Mapping[str, Any]) -> float:
    first_text = _content_text(first)
    second_text = _content_text(second)
    if not first_text or not second_text:
        return 0.0
    return round(SequenceMatcher(None, first_text, second_text).ratio(), 4)


def plan_keyframe_offsets(duration_seconds: int | float, interval_seconds: int = 15) -> List[int]:
    duration = max(0, int(duration_seconds or 0))
    if duration <= 0:
        return []
    if duration <= 60:
        return sorted({0, duration // 2, duration})
    offsets = set(range(0, duration + 1, max(1, int(interval_seconds))))
    offsets.update({0, duration // 2, duration})
    return sorted(offsets)


def select_comment_samples(
    comments: Iterable[Mapping[str, Any]],
    hot_limit: int = 30,
    recent_limit: int = 30,
    keywords: Iterable[str] = (),
) -> List[Dict[str, Any]]:
    rows = [dict(comment) for comment in comments]
    selected: Dict[str, Dict[str, Any]] = {}
    keyword_list = [str(keyword).lower() for keyword in keywords if str(keyword).strip()]

    def add(comment: Mapping[str, Any]) -> None:
        key = _clean(comment.get("id")) or _sha1(_content_text(comment))
        if key:
            selected[key] = dict(comment)

    for comment in sorted(rows, key=lambda item: _to_int(item.get("likes")), reverse=True)[:hot_limit]:
        add(comment)
    for comment in sorted(rows, key=lambda item: _clean(item.get("published_at")))[:recent_limit]:
        add(comment)
    for comment in rows:
        text = _clean(comment.get("text") or comment.get("body")).lower()
        if comment.get("is_author_reply") or any(keyword in text for keyword in keyword_list):
            add(comment)
    return list(selected.values())


def build_daily_bundle_manifest(
    bundle_date: str,
    node_id: str,
    counts: Mapping[str, int],
    files: Iterable[Mapping[str, Any]],
    errors: Iterable[Mapping[str, Any] | str],
) -> Dict[str, Any]:
    return {
        "version": "0.2.0",
        "bundle_date": bundle_date,
        "node_id": node_id,
        "counts": dict(counts),
        "files": [dict(file_info) for file_info in files],
        "errors": [dict(error) if isinstance(error, Mapping) else {"message": str(error)} for error in errors],
        "contains_raw_media": False,
        "handoff": "local_bundle_for_super_brain",
    }


def _canonical_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _content_text(item: Mapping[str, Any]) -> str:
    return _clean(" ".join(str(item.get(key, "")) for key in ("title", "body", "description", "text", "transcript"))).lower()


def _first_alias(text: str, alias_map: Mapping[str, Iterable[str]]) -> str:
    for canonical, aliases in alias_map.items():
        if any(alias.lower() in text for alias in aliases):
            return canonical
    return ""


def _fallback_topic(text: str) -> str:
    tokens = [token for token in _TOKEN_RE.findall(text) if token not in {"今天", "游客", "阳朔", "wuhan", "yangshuo"}]
    return "-".join(tokens[:3]) if tokens else "general"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _sha1(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
