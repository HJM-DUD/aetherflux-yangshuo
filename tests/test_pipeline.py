import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aetherflux.deepseek import DeepSeekAdvisorError
from aetherflux.pipeline import run_ingest, run_review
from aetherflux.storage import IntelligenceStore


class PipelineTests(unittest.TestCase):
    def test_ingest_and_review_pipeline_is_config_driven(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            directions_path = root / "directions.json"
            seed_path = root / "seed.json"
            db_path = root / "intel.db"
            directions_path.write_text(
                json.dumps(
                    {
                        "places": ["Yangshuo", "Yulong River", "遇龙河"],
                        "themes": [
                            {"id": "foreign_signal", "label": "外国游客信号", "keywords": ["yangshuo", "reddit"], "weight": 18},
                            {"id": "opportunity", "label": "项目机会", "keywords": ["cycling", "route"], "weight": 12},
                        ],
                        "platform_weights": {"reddit": 13},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            seed_path.write_text(
                json.dumps(
                    [
                        {
                            "title": "Yangshuo cycling route gets attention on Reddit",
                            "body": "Travelers ask for a safe Yulong River cycling route.",
                            "source": "Reddit",
                            "platform": "reddit",
                            "url": "https://example.com/reddit-yangshuo",
                            "published_at": "2026-05-20T10:00:00Z",
                            "engagement": {"likes": 80, "comments": 12},
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            store = IntelligenceStore(db_path)
            store.initialize()

            with patch("aetherflux.pipeline.AdvisorService") as advisor_service:
                advisor_service.from_env.return_value.enrich_candidates.side_effect = lambda candidates: [
                    {
                        **dict(candidate),
                        "display": {
                            "title_zh": candidate["title"],
                            "title_en": "Yangshuo cycling route gets attention",
                            "summary_zh": candidate["summary"],
                            "summary_en": "Foreign travelers ask about the Yulong River route.",
                        },
                        "translation_status": "translated",
                        "advisor_notes": {"status": "ok"},
                        "cross_check": {"status": "needs_more_sources"},
                        "geo_risk": {"probability": 0.2, "level": "low", "reasons": []},
                    }
                    for candidate in candidates
                ]
                ingest_result = run_ingest(store, directions_path, seed_path)
                draft = run_review(store, webhook_url="")

            self.assertEqual(ingest_result["stored"], 1)
            self.assertEqual(draft["status"], "draft")
            self.assertEqual(draft["selected"][0]["category"], "foreign_signal")

    def test_review_stops_without_saving_draft_when_deepseek_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            directions_path = root / "directions.json"
            seed_path = root / "seed.json"
            db_path = root / "intel.db"
            directions_path.write_text(
                json.dumps({"places": ["阳朔"], "themes": [], "platform_weights": {"xiaohongshu": 13}}, ensure_ascii=False),
                encoding="utf-8",
            )
            seed_path.write_text(
                json.dumps(
                    [
                        {
                            "title": "阳朔首采",
                            "body": "等待 DeepSeek 翻译",
                            "source": "小红书",
                            "platform": "xiaohongshu",
                            "url": "https://example.com/xhs",
                            "published_at": "2026-05-20T10:00:00Z",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            store = IntelligenceStore(db_path)
            store.initialize()
            run_ingest(store, directions_path, seed_path)

            with patch("aetherflux.pipeline.AdvisorService") as advisor_service:
                advisor_service.from_env.return_value.enrich_candidates.side_effect = DeepSeekAdvisorError(
                    "DeepSeek advisor failed after 3 attempts: timed out"
                )
                with self.assertRaisesRegex(DeepSeekAdvisorError, "DeepSeek advisor failed"):
                    run_review(store, webhook_url="")

            self.assertEqual(store.latest_review_draft(), {})


if __name__ == "__main__":
    unittest.main()
