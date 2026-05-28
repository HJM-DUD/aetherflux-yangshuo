"""Config-driven ingestion and review pipeline."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Mapping

from .advisor import AdvisorService
from .review import create_review_draft
from .scoring import build_candidate, merge_duplicates
from .storage import IntelligenceStore


def load_json(path: Path | str, default: Any) -> Any:
    target = Path(path)
    if not target.exists():
        return default
    return json.loads(target.read_text(encoding="utf-8"))


def run_ingest(store: IntelligenceStore, directions_path: Path | str, seed_path: Path | str) -> Dict[str, Any]:
    directions = load_json(directions_path, {})
    raw_items = load_json(seed_path, [])
    candidates = [build_candidate(raw_item, directions) for raw_item in raw_items]
    merged = merge_duplicates(candidates)
    store.upsert_candidates(merged)
    return {
        "raw": len(raw_items),
        "stored": len(merged),
        "duplicates_merged": max(0, len(raw_items) - len(merged)),
    }


def run_review(store: IntelligenceStore, webhook_url: str = "", top_n: int = 20) -> Dict[str, Any]:
    candidates = [candidate for candidate in store.list_candidates(limit=300) if candidate.get("human_status") != "rejected"]
    candidates = AdvisorService.from_env().enrich_candidates(candidates)
    store.upsert_candidates(candidates)
    draft = create_review_draft(candidates, top_n=top_n)
    store.save_review_draft(draft)
    if webhook_url:
        send_webhook(webhook_url, build_webhook_payload(draft))
    return draft


def build_webhook_payload(draft: Mapping[str, Any]) -> Dict[str, Any]:
    selected = list(draft.get("selected", []))
    return {
        "type": "yangshuo_intelligence_review",
        "title": "阳朔旅游情报待审稿已生成",
        "summary": draft.get("summary", ""),
        "generated_at": draft.get("generated_at"),
        "selected_count": len(selected),
        "top_items": [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "score": item.get("score"),
                "category": item.get("category"),
            }
            for item in selected[:5]
        ],
        "questions_for_human": list(draft.get("questions_for_human", [])),
        "auto_publish": False,
    }


def send_webhook(webhook_url: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    body = json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "AetherFlux-Yangshuo/0.1"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return {"ok": True, "status": response.status}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": str(exc)}
