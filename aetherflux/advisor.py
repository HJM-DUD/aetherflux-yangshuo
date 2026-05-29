"""Advisor enrichment: translation, cross-check hints, and GEO risk."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

from .deepseek import DeepSeekAdvisorError, DeepSeekClient, DeepSeekConfig


def apply_fallback_advisor(candidates: Iterable[Mapping[str, Any]], reason: str = "DEEPSEEK_API_KEY is not configured") -> List[Dict[str, Any]]:
    return [_with_defaults(dict(candidate), reason) for candidate in candidates]


class AdvisorService:
    def __init__(self, client: Any | None = None, disabled_reason: str = "DEEPSEEK_API_KEY is not configured") -> None:
        self.client = client
        self.disabled_reason = disabled_reason

    @classmethod
    def from_env(cls) -> "AdvisorService":
        config = DeepSeekConfig.from_env()
        if not config.enabled:
            return cls(client=None, disabled_reason="DEEPSEEK_API_KEY is not configured")
        return cls(client=DeepSeekClient(config))

    def enrich_candidates(self, candidates: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        base = [dict(candidate) for candidate in candidates]
        if not base:
            return []
        if self.client is None:
            raise DeepSeekAdvisorError(self.disabled_reason)

        response = self.client.advise_candidates(base)

        advisor_items = {str(item.get("id")): item for item in response.get("items", []) if isinstance(item, Mapping)}
        enriched = []
        for candidate in base:
            enriched.append(_merge_advisor_item(_with_defaults(candidate, ""), advisor_items.get(str(candidate.get("id")), {})))
        return enriched


def _with_defaults(candidate: Dict[str, Any], reason: str) -> Dict[str, Any]:
    display = dict(candidate.get("display") or {})
    language = candidate.get("language")
    title = str(candidate.get("title", ""))
    summary = str(candidate.get("summary", ""))
    if language == "en":
        display.setdefault("title_en", title)
        display.setdefault("summary_en", summary)
        display.setdefault("title_zh", "")
        display.setdefault("summary_zh", "")
    else:
        display.setdefault("title_zh", title)
        display.setdefault("summary_zh", summary)
        display.setdefault("title_en", "")
        display.setdefault("summary_en", "")
    candidate["display"] = display
    candidate.setdefault("translation_status", "untranslated")
    advisor_summary = "使用本地默认审议字段。"
    if reason:
        advisor_summary = "DeepSeek 智库层请求失败，当前使用规则审议。"
        if "timed out" in reason.lower() or "timeout" in reason.lower():
            advisor_summary = "DeepSeek 智库层请求超时，当前使用规则审议。"
        elif "not configured" in reason:
            advisor_summary = "DeepSeek 智库层未启用，当前仅使用规则审议。"
    candidate.setdefault(
        "advisor_notes",
        {
            "status": "disabled" if reason else "fallback",
            "confidence": None,
            "summary": advisor_summary,
            "opportunities": [],
            "risks": [reason] if reason else [],
            "human_questions": [],
        },
    )
    candidate.setdefault(
        "cross_check",
        {
            "status": "unverified",
            "supporting_sources": [],
            "conflicting_sources": [],
            "needs_more_sources": True,
            "reasoning": "尚未经过跨平台交叉验证。",
        },
    )
    candidate.setdefault(
        "geo_risk",
        {
            "probability": _fallback_geo_probability(candidate),
            "level": _fallback_geo_level(candidate),
            "reasons": _fallback_geo_reasons(candidate),
        },
    )
    candidate.setdefault("tags", _fallback_tags(candidate))
    return candidate


def _merge_advisor_item(candidate: Dict[str, Any], advisor_item: Mapping[str, Any]) -> Dict[str, Any]:
    for key in ("display", "advisor_notes", "cross_check", "geo_risk"):
        value = advisor_item.get(key)
        if isinstance(value, Mapping):
            merged = dict(candidate.get(key) or {})
            merged.update(dict(value))
            if key == "geo_risk":
                merged = _normalize_geo_risk(merged)
            candidate[key] = merged
    if advisor_item.get("translation_status"):
        candidate["translation_status"] = advisor_item["translation_status"]
    for key in ("tags", "advisor_tags"):
        value = advisor_item.get(key)
        if isinstance(value, list):
            candidate[key] = [str(item).strip() for item in value if str(item).strip()][:8]
    return candidate


def _normalize_geo_risk(geo_risk: Dict[str, Any]) -> Dict[str, Any]:
    probability = geo_risk.get("probability")
    if isinstance(probability, str):
        normalized = probability.strip().lower()
        if normalized.endswith("%"):
            try:
                geo_risk["probability"] = round(float(normalized.rstrip("%")) / 100, 2)
                return geo_risk
            except ValueError:
                pass
        level_map = {"low": 0.2, "medium": 0.5, "high": 0.8}
        if normalized in level_map:
            geo_risk["probability"] = level_map[normalized]
            geo_risk.setdefault("level", normalized)
            return geo_risk
    try:
        geo_risk["probability"] = round(float(probability), 2)
    except (TypeError, ValueError):
        level = str(geo_risk.get("level", "low")).lower()
        geo_risk["probability"] = {"low": 0.2, "medium": 0.5, "high": 0.8}.get(level, 0.0)
    return geo_risk


def _fallback_geo_probability(candidate: Mapping[str, Any]) -> float:
    probability = 0.12
    if candidate.get("platform") in {"xiaohongshu", "douyin", "tiktok", "instagram"}:
        probability += 0.08
    if "项目机会" in candidate.get("signals", []):
        probability += 0.08
    if len(candidate.get("evidence", [])) <= 1:
        probability += 0.07
    return round(min(probability, 0.55), 2)


def _fallback_geo_level(candidate: Mapping[str, Any]) -> str:
    probability = _fallback_geo_probability(candidate)
    if probability >= 0.45:
        return "high"
    if probability >= 0.25:
        return "medium"
    return "low"


def _fallback_geo_reasons(candidate: Mapping[str, Any]) -> List[str]:
    reasons = ["尚未完成跨平台交叉验证"]
    if candidate.get("platform") in {"xiaohongshu", "douyin", "tiktok", "instagram"}:
        reasons.append("社交平台内容可能存在营销叙事包装")
    if "项目机会" in candidate.get("signals", []):
        reasons.append("内容具有商业转化指向，需要谨慎采信")
    return reasons


def _fallback_tags(candidate: Mapping[str, Any]) -> List[str]:
    tags: List[str] = []
    for key in ("signals", "category", "platform"):
        value = candidate.get(key)
        if isinstance(value, list):
            tags.extend(str(item).strip() for item in value if str(item).strip())
        elif value:
            tags.append(str(value).strip())
    return list(dict.fromkeys(tags))[:8]
