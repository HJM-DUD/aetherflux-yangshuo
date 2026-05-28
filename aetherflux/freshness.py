"""Freshness parsing for platform-visible publish time strings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass(frozen=True)
class FreshnessResult:
    published_at: str
    status: str
    age_hours: Optional[float]
    reason: str


def evaluate_freshness(raw_value: str, now: datetime | None = None, window_hours: int = 24) -> FreshnessResult:
    now_dt = now or datetime.now().astimezone()
    parsed = parse_platform_time(raw_value, now_dt)
    if parsed is None:
        return FreshnessResult("", "unknown", None, "unparsed_publish_time")
    age = (now_dt.replace(tzinfo=None) - parsed.replace(tzinfo=None)).total_seconds() / 3600
    if age < -1:
        return FreshnessResult(parsed.isoformat(timespec="minutes"), "unknown", age, "future_publish_time")
    if age <= window_hours:
        return FreshnessResult(parsed.isoformat(timespec="minutes"), "recent", round(age, 2), "within_window")
    return FreshnessResult(parsed.isoformat(timespec="minutes"), "stale", round(age, 2), "outside_window")


def parse_platform_time(raw_value: str, now: datetime | None = None) -> datetime | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    now_dt = (now or datetime.now()).replace(tzinfo=None)
    if any(marker in text for marker in ("刚刚", "刚才")):
        return now_dt

    minute_match = re.search(r"(\d+)\s*分钟(?:前)?", text)
    if minute_match:
        return now_dt - timedelta(minutes=int(minute_match.group(1)))

    hour_match = re.search(r"(\d+)\s*小时(?:前)?", text)
    if hour_match:
        return now_dt - timedelta(hours=int(hour_match.group(1)))

    today_match = re.search(r"今天\s*(\d{1,2}):(\d{2})", text)
    if today_match:
        return now_dt.replace(hour=int(today_match.group(1)), minute=int(today_match.group(2)), second=0, microsecond=0)

    yesterday_match = re.search(r"昨天\s*(\d{1,2}):(\d{2})", text)
    if yesterday_match:
        base = now_dt - timedelta(days=1)
        return base.replace(hour=int(yesterday_match.group(1)), minute=int(yesterday_match.group(2)), second=0, microsecond=0)

    ymd_match = re.search(r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})", text)
    if ymd_match:
        return datetime(int(ymd_match.group(1)), int(ymd_match.group(2)), int(ymd_match.group(3)))

    md_match = re.search(r"(\d{1,2})月(\d{1,2})日?", text)
    if md_match:
        return datetime(now_dt.year, int(md_match.group(1)), int(md_match.group(2)))

    return None
