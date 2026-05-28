"""Public payload builders for dashboard and agent-facing APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping

from .storage import IntelligenceStore


def build_public_payloads(store: IntelligenceStore) -> Dict[str, Any]:
    approved = store.list_approved(limit=200)
    selected = approved[:50]
    opportunities = _filter_by_signal(approved, "项目机会")
    foreign_signals = [item for item in approved if item.get("category") == "foreign_signal" or item.get("language") == "en"]
    risks = _filter_by_signal(approved, "风险预警")
    return {
        "generated_at": _utc_now(),
        "selected": selected,
        "daily": _daily_payload(selected, opportunities, foreign_signals, risks),
        "opportunities": opportunities,
        "foreign_signals": foreign_signals,
        "risks": risks,
        "content_briefs": _content_briefs(opportunities, foreign_signals, risks),
    }


def candidate_to_api(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "id": candidate.get("id"),
        "title": candidate.get("title"),
        "summary": candidate.get("summary"),
        "source": candidate.get("source"),
        "platform": candidate.get("platform"),
        "url": candidate.get("url"),
        "published_at": candidate.get("published_at"),
        "language": candidate.get("language"),
        "category": candidate.get("category"),
        "signals": candidate.get("signals", []),
        "score": candidate.get("score", 0),
        "human_status": candidate.get("human_status", "pending"),
        "human_note": candidate.get("human_note", ""),
        "evidence": candidate.get("evidence", []),
        "display": candidate.get("display", {}),
        "translation_status": candidate.get("translation_status", "untranslated"),
        "advisor_notes": candidate.get("advisor_notes", {}),
        "cross_check": candidate.get("cross_check", {}),
        "geo_risk": candidate.get("geo_risk", {}),
    }


def _filter_by_signal(items: List[Mapping[str, Any]], signal: str) -> List[Dict[str, Any]]:
    return [dict(item) for item in items if signal in item.get("signals", [])]


def _daily_payload(selected: List[Mapping[str, Any]], opportunities: List[Mapping[str, Any]], foreign: List[Mapping[str, Any]], risks: List[Mapping[str, Any]]) -> Dict[str, Any]:
    lead = selected[0] if selected else {}
    return {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "lead": {
            "title": lead.get("title", "今日暂无已确认精选"),
            "paragraph": lead.get("summary", "等待人工确认后生成日报。"),
        },
        "sections": [
            {"label": "今日精选", "items": [candidate_to_api(item) for item in selected[:12]]},
            {"label": "国内外差异", "items": [candidate_to_api(item) for item in foreign[:8]]},
            {"label": "项目机会", "items": [candidate_to_api(item) for item in opportunities[:8]]},
            {"label": "风险预警", "items": [candidate_to_api(item) for item in risks[:8]]},
        ],
    }


def _content_briefs(opportunities: List[Mapping[str, Any]], foreign: List[Mapping[str, Any]], risks: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    briefs: List[Dict[str, Any]] = []
    seen_ids = set()
    for item in list(opportunities[:5]) + list(foreign[:3]) + list(risks[:3]):
        item_id = item.get("id")
        if item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        briefs.append(
            {
                "source_item_id": item_id,
                "angle": _angle_for(item),
                "evidence_urls": [evidence.get("url") for evidence in item.get("evidence", []) if evidence.get("url")],
                "priority": item.get("score", 0),
            }
        )
    return briefs


def _angle_for(item: Mapping[str, Any]) -> str:
    if "风险预警" in item.get("signals", []):
        return f"内部风险观察：{item.get('title')}"
    if item.get("category") == "foreign_signal" or item.get("language") == "en":
        return f"外国游客怎么看阳朔：{item.get('title')}"
    return f"可转化为内容/项目线索：{item.get('title')}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
