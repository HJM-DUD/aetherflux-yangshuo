"""Mac-side Codex review orchestration primitives."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping

from .advisor import apply_fallback_advisor


ROLE_LABELS = {
    "chief_editor": "主编 Agent",
    "domestic_social": "国内社媒 Agent",
    "foreign_traveler": "外国游客 Agent",
    "opportunity": "项目机会 Agent",
    "risk": "风险 Agent",
    "fact_check": "事实核查 Agent",
    "editor": "编辑 Agent",
}


def create_review_draft(candidates: Iterable[Mapping[str, Any]], top_n: int = 20) -> Dict[str, Any]:
    ready_candidates = apply_fallback_advisor(candidates, reason="")
    ordered = sorted((dict(candidate) for candidate in ready_candidates), key=lambda item: int(item.get("score", 0)), reverse=True)
    selected = [candidate for candidate in ordered if int(candidate.get("score", 0)) >= 45][:top_n]
    role_assessments = _build_role_assessments(selected, ordered)
    questions = _questions_for_human(selected)

    return {
        "id": "draft-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "status": "draft",
        "auto_publish": False,
        "generated_at": _utc_now(),
        "selected": selected,
        "role_assessments": role_assessments,
        "questions_for_human": questions,
        "summary": _draft_summary(selected),
        "next_action": "请人工确认、驳回或调整权重；确认后才进入网页精选和正式 API。",
    }


def _build_role_assessments(selected: List[Mapping[str, Any]], all_candidates: List[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    foreign = [item for item in selected if item.get("language") == "en" or item.get("category") == "foreign_signal"]
    risks = [item for item in selected if "风险预警" in item.get("signals", []) or item.get("category") == "risk"]
    opportunities = [item for item in selected if "项目机会" in item.get("signals", []) or item.get("category") == "opportunity"]
    domestic = [item for item in selected if item.get("platform") in {"xiaohongshu", "douyin", "weibo", "dianping"}]

    return {
        "chief_editor": {
            "label": ROLE_LABELS["chief_editor"],
            "view": f"候选池 {len(all_candidates)} 条，建议进入待审 {len(selected)} 条。",
            "priority_ids": [item.get("id") for item in selected[:5]],
        },
        "domestic_social": {
            "label": ROLE_LABELS["domestic_social"],
            "view": f"国内社媒候选 {len(domestic)} 条，重点看小红书/抖音的内容爆点和重复出现的抱怨。",
            "priority_ids": [item.get("id") for item in domestic[:5]],
        },
        "foreign_traveler": {
            "label": ROLE_LABELS["foreign_traveler"],
            "view": f"外语/外网信号 {len(foreign)} 条，重点看外国游客的误解、动线阻碍和未被满足需求。",
            "priority_ids": [item.get("id") for item in foreign[:5]],
        },
        "opportunity": {
            "label": ROLE_LABELS["opportunity"],
            "view": f"项目机会 {len(opportunities)} 条，可转为内容选题、线路产品、合作切口。",
            "priority_ids": [item.get("id") for item in opportunities[:5]],
        },
        "risk": {
            "label": ROLE_LABELS["risk"],
            "view": f"风险候选 {len(risks)} 条，建议优先人工核查证据链和发布时间。",
            "priority_ids": [item.get("id") for item in risks[:5]],
        },
        "fact_check": {
            "label": ROLE_LABELS["fact_check"],
            "view": "所有待审条目必须保留来源链接；重复来源越多，证据强度越高。",
            "priority_ids": [item.get("id") for item in selected if item.get("evidence")][:5],
        },
        "editor": {
            "label": ROLE_LABELS["editor"],
            "view": "发布前需把标题改成决策口吻，摘要说明为什么值得今天关注。",
            "priority_ids": [item.get("id") for item in selected[:5]],
        },
    }


def _questions_for_human(selected: List[Mapping[str, Any]]) -> List[str]:
    questions = []
    if any(item.get("category") == "foreign_signal" for item in selected):
        questions.append("外网信号是否需要单独进入「国内外差异」栏目？")
    if any("风险预警" in item.get("signals", []) for item in selected):
        questions.append("风险类条目是否需要降低公开表达强度，只作为内部提醒？")
    if any(int(item.get("score", 0)) >= 80 for item in selected):
        questions.append("80 分以上条目是否进入今日精选头部？")
    return questions or ["请确认今天是否有条目进入精选和日报。"]


def _draft_summary(selected: List[Mapping[str, Any]]) -> str:
    if not selected:
        return "今日暂无达到待审阈值的阳朔旅游情报。"
    top = selected[0]
    return f"今日建议待审 {len(selected)} 条，最高权重为「{top.get('title')}」（{top.get('score')} 分）。"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
