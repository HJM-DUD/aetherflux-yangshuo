"""Hybrid query planning for high-volume daily collection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Mapping


DEFAULT_SEGMENTS = ["景区", "民宿", "酒店", "旅游餐饮", "旅拍", "骑行", "亲子", "研学", "疗愈"]
DEFAULT_RISK_TERMS = ["避雷", "排队", "投诉", "宰客", "堵车", "价格"]
DEFAULT_OPPORTUNITY_TERMS = ["攻略", "路线", "新玩法", "小众", "体验", "vlog"]


@dataclass(frozen=True)
class PlannedQuery:
    query: str
    source: str
    priority: int


def build_hybrid_queries(config: Mapping[str, Any], directions_path: str | Path = "config/directions.json") -> List[PlannedQuery]:
    manual = _as_list(config.get("manual_queries") or config.get("queries"))
    segments = _as_list(config.get("segments")) or DEFAULT_SEGMENTS
    risk_terms = _as_list(config.get("risk_terms")) or DEFAULT_RISK_TERMS
    opportunity_terms = _as_list(config.get("opportunity_terms")) or DEFAULT_OPPORTUNITY_TERMS
    hermes_terms = _as_list(config.get("hermes_queries"))
    places = _places_from_directions(directions_path)

    rows: List[PlannedQuery] = []
    for query in manual:
        rows.append(PlannedQuery(query=query, source="manual", priority=100))
    for place in places[:8]:
        rows.append(PlannedQuery(query=f"{place} 旅游", source="rule_place", priority=80))
        for segment in segments[:6]:
            rows.append(PlannedQuery(query=f"{place} {segment}", source="rule_segment", priority=70))
        for term in opportunity_terms[:6]:
            rows.append(PlannedQuery(query=f"{place} {term}", source="rule_opportunity", priority=60))
        for term in risk_terms[:6]:
            rows.append(PlannedQuery(query=f"{place} {term}", source="rule_risk", priority=65))
    for query in hermes_terms:
        rows.append(PlannedQuery(query=query, source="hermes_explore", priority=75))

    return _dedupe_queries(rows)


def _places_from_directions(path: str | Path) -> List[str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ["阳朔", "遇龙河", "西街", "兴坪", "十里画廊"]
    places = [str(place).strip() for place in data.get("places", []) if str(place).strip()]
    chinese_places = [place for place in places if any("\u4e00" <= char <= "\u9fff" for char in place)]
    return chinese_places or places or ["阳朔"]


def _as_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]
    if isinstance(value, Iterable):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def _dedupe_queries(rows: Iterable[PlannedQuery]) -> List[PlannedQuery]:
    seen = set()
    result: List[PlannedQuery] = []
    for row in sorted(rows, key=lambda item: item.priority, reverse=True):
        key = row.query.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result
