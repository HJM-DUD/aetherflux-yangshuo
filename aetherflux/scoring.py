"""Low-token candidate scoring for Yangshuo tourism intelligence."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_WORD_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", re.IGNORECASE)

_STOPWORDS = {
    "今天",
    "游客",
    "反馈",
    "很多",
    "同一个",
    "问题",
    "不同",
    "平台",
    "出现",
    "yangshuo",
    "travel",
    "forum",
    "users",
}

_PLACE_ALIASES = {
    "yangshuo": ("阳朔", "yangshuo"),
    "遇龙河": ("遇龙河", "yulong", "yulong river"),
    "西街": ("西街", "west street"),
    "兴坪": ("兴坪", "xingping"),
    "十里画廊": ("十里画廊", "ten-mile gallery", "ten mile gallery"),
    "漓江": ("漓江", "li river", "lijiang river"),
    "相公山": ("相公山", "xiangong mountain"),
}

_INTENT_ALIASES = {
    "queue_ticket": ("排队", "票务", "竹筏", "queue", "ticket", "wait", "waiting", "confusing"),
    "price_complaint": ("宰客", "价格", "overpriced", "scam", "ripoff", "complaint"),
    "route_content": ("路线", "骑行", "cycling", "itinerary", "route", "vlog"),
    "photo_trip": ("旅拍", "拍照", "photo", "photography", "portrait"),
    "hotel_stay": ("民宿", "酒店", "hotel", "hostel", "homestay"),
}


def clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_language(text: str) -> str:
    cjk_count = len(_CJK_RE.findall(text))
    latin_count = len(re.findall(r"[A-Za-z]", text))
    if cjk_count and cjk_count >= latin_count * 0.35:
        return "zh"
    if latin_count:
        return "en"
    return "unknown"


def make_dedupe_key(raw_item: Mapping[str, Any]) -> str:
    text = clean_text(f"{raw_item.get('title', '')} {raw_item.get('body', '')}").lower()
    place = _first_alias_match(text, _PLACE_ALIASES) or "general"
    intent = _first_alias_match(text, _INTENT_ALIASES) or _fallback_topic(text)
    return f"{place}:{intent}"


def build_candidate(raw_item: Mapping[str, Any], directions: Mapping[str, Any]) -> Dict[str, Any]:
    title = clean_text(raw_item.get("title"))
    body = clean_text(raw_item.get("body"))
    joined = f"{title} {body}".strip()
    lower_joined = joined.lower()
    language = detect_language(joined)
    matched_themes = _match_themes(lower_joined, directions.get("themes", []))
    signals = [theme["label"] for theme in matched_themes]
    category = matched_themes[0]["id"] if matched_themes else "general"
    score = _score_item(raw_item, directions, matched_themes, lower_joined)
    dedupe_key = make_dedupe_key(raw_item)
    url = clean_text(raw_item.get("url"))
    item_id = _stable_id(dedupe_key, url or title)

    return {
        "id": item_id,
        "dedupe_key": dedupe_key,
        "title": title or "未命名情报",
        "summary": _summarize(title, body),
        "body": body,
        "source": clean_text(raw_item.get("source")) or clean_text(raw_item.get("platform")) or "unknown",
        "platform": clean_text(raw_item.get("platform")) or "unknown",
        "url": url,
        "published_at": clean_text(raw_item.get("published_at")) or _utc_now(),
        "language": language,
        "category": category,
        "signals": signals,
        "score": score,
        "raw": dict(raw_item),
        "evidence": [
            {
                "url": url,
                "source": clean_text(raw_item.get("source")) or clean_text(raw_item.get("platform")) or "unknown",
                "published_at": clean_text(raw_item.get("published_at")),
                "quote": body[:240] if body else title[:240],
            }
        ],
        "scoring_notes": _scoring_notes(raw_item, matched_themes),
    }


def merge_duplicates(candidates: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        key = str(candidate.get("dedupe_key") or candidate.get("id"))
        current = grouped.get(key)
        if current is None:
            grouped[key] = dict(candidate)
            grouped[key]["duplicate_count"] = 0
            grouped[key]["duplicate_sources"] = [candidate.get("source") or candidate.get("platform") or "unknown"]
            continue

        current["duplicate_count"] = int(current.get("duplicate_count", 0)) + 1
        current["score"] = max(int(current.get("score", 0)), int(candidate.get("score", 0))) + 3
        current["score"] = min(100, current["score"])
        current["signals"] = sorted(set(current.get("signals", [])) | set(candidate.get("signals", [])))
        current["evidence"] = list(current.get("evidence", [])) + list(candidate.get("evidence", []))
        source = candidate.get("source") or candidate.get("platform") or "unknown"
        if source not in current["duplicate_sources"]:
            current["duplicate_sources"].append(source)
    return sorted(grouped.values(), key=lambda item: int(item.get("score", 0)), reverse=True)


def _match_themes(text: str, themes: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    matched: List[Dict[str, Any]] = []
    for theme in themes:
        keywords = [str(keyword).lower() for keyword in theme.get("keywords", [])]
        hits = [keyword for keyword in keywords if keyword and keyword in text]
        if hits:
            matched.append(
                {
                    "id": str(theme.get("id", "general")),
                    "label": str(theme.get("label", theme.get("id", "general"))),
                    "weight": int(theme.get("weight", 8)),
                    "hits": hits,
                }
            )
    matched.sort(key=lambda theme: theme["weight"], reverse=True)
    return matched


def _score_item(raw_item: Mapping[str, Any], directions: Mapping[str, Any], themes: List[Mapping[str, Any]], text: str) -> int:
    platform = str(raw_item.get("platform", "unknown")).lower()
    platform_weights = directions.get("platform_weights", {})
    score = 20 + int(platform_weights.get(platform, 6))
    score += min(38, sum(int(theme.get("weight", 0)) for theme in themes))
    score += _engagement_score(raw_item.get("engagement", {}))
    if any(str(place).lower() in text for place in directions.get("places", [])):
        score += 8
    if detect_language(text) == "en":
        score += 5
    return max(0, min(score, 100))


def _engagement_score(engagement: Any) -> int:
    if not isinstance(engagement, Mapping):
        return 0
    likes = int(engagement.get("likes", 0) or 0)
    comments = int(engagement.get("comments", 0) or 0)
    shares = int(engagement.get("shares", 0) or 0)
    raw = likes * 0.03 + comments * 0.35 + shares * 0.5
    return min(14, int(raw))


def _scoring_notes(raw_item: Mapping[str, Any], themes: List[Mapping[str, Any]]) -> List[str]:
    notes = []
    if themes:
        notes.append("命中主题：" + "、".join(theme["label"] for theme in themes))
    platform = clean_text(raw_item.get("platform"))
    if platform:
        notes.append(f"平台权重：{platform}")
    if raw_item.get("engagement"):
        notes.append("含互动数据，已纳入基础热度")
    return notes


def _first_alias_match(text: str, alias_map: Mapping[str, Iterable[str]]) -> str:
    for canonical, aliases in alias_map.items():
        if any(alias.lower() in text for alias in aliases):
            return canonical
    return ""


def _fallback_topic(text: str) -> str:
    tokens = [token for token in _WORD_RE.findall(text) if token not in _STOPWORDS]
    return "-".join(tokens[:3]) if tokens else "general"


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"cand-{digest}"


def _summarize(title: str, body: str) -> str:
    body = clean_text(body)
    if body:
        return body[:220] + ("..." if len(body) > 220 else "")
    return title[:220]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
