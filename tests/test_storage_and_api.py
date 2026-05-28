import tempfile
import unittest
from pathlib import Path

from aetherflux.api import build_public_payloads
from aetherflux.storage import IntelligenceStore


class StorageAndApiTests(unittest.TestCase):
    def test_approved_items_flow_to_public_payloads(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "intel.db"
            store = IntelligenceStore(db_path)
            store.initialize()
            store.upsert_candidate(
                {
                    "id": "cand-1",
                    "title": "遇龙河外国游客排队反馈升温",
                    "summary": "外网讨论集中在票务指引不清楚。",
                    "score": 84,
                    "category": "foreign_signal",
                    "signals": ["外国游客信号", "风险预警"],
                    "language": "zh",
                    "platform": "reddit",
                    "published_at": "2026-05-20T08:00:00Z",
                    "evidence": [{"url": "https://example.com/a", "source": "Reddit"}],
                    "display": {
                        "title_zh": "遇龙河外国游客排队反馈升温",
                        "title_en": "Foreign visitors report Yulong River queue issues",
                        "summary_zh": "外网讨论集中在票务指引不清楚。",
                        "summary_en": "Foreign discussions focus on unclear ticket guidance.",
                    },
                    "translation_status": "translated",
                    "cross_check": {
                        "status": "needs_more_sources",
                        "supporting_sources": [],
                        "conflicting_sources": [],
                        "needs_more_sources": True,
                        "reasoning": "需要更多来源。",
                    },
                    "geo_risk": {"probability": 0.2, "level": "low", "reasons": []},
                }
            )
            store.set_human_decision("cand-1", "approved", weight_override=91, note="进入今日精选")

            payloads = build_public_payloads(store)

            self.assertEqual(payloads["selected"][0]["id"], "cand-1")
            self.assertEqual(payloads["selected"][0]["score"], 91)
            self.assertEqual(payloads["selected"][0]["display"]["title_en"], "Foreign visitors report Yulong River queue issues")
            self.assertEqual(payloads["selected"][0]["cross_check"]["status"], "needs_more_sources")
            self.assertEqual(payloads["selected"][0]["geo_risk"]["level"], "low")
            self.assertEqual(payloads["foreign_signals"][0]["id"], "cand-1")
            self.assertEqual(payloads["risks"][0]["id"], "cand-1")
            brief_ids = [brief["source_item_id"] for brief in payloads["content_briefs"]]
            self.assertEqual(brief_ids, ["cand-1"])


if __name__ == "__main__":
    unittest.main()
