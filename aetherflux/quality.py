"""Quality gates for live-collected public page items."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping


NOISE_MARKERS = [
    "安全限制",
    "访问链接异常",
    "300017",
    "用户服务协议",
    "未找到该协议",
    "沪ICP备",
    "京ICP备",
    "营业执照",
    "首页 点点 ai RED",
    "返回首页",
]


def classify_quality(item: Mapping[str, Any]) -> Dict[str, Any]:
    text = f"{item.get('title') or ''} {item.get('body') or ''}"
    url = str(item.get("url") or "")
    cover = str((item.get("media") or {}).get("cover_url") or "")
    reasons: List[str] = []
    score = 0

    if any(marker in text for marker in NOISE_MARKERS) or "/agreements" in url:
        reasons.append("blocked_or_noise_page")
    if not url.startswith("http"):
        reasons.append("missing_url")
    if len(str(item.get("title") or "").strip()) >= 6:
        score += 20
    if len(str(item.get("body") or "").strip()) >= 30:
        score += 30
    else:
        reasons.append("body_too_short")
    if url.startswith("http"):
        score += 20
    if cover and not cover.startswith("data:image"):
        score += 10
    elif cover.startswith("data:image"):
        reasons.append("data_image_cover")
    if ((item.get("evidence") or {}).get("screenshot_path")):
        score += 20

    if "blocked_or_noise_page" in reasons or score < 50:
        return {"quality_status": "rejected", "quality_score": score, "reject_reason": ",".join(reasons)}
    return {"quality_status": "accepted", "quality_score": score, "reject_reason": ""}
