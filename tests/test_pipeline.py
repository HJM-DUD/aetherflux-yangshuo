import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

            with patch.dict("os.environ", {"DEEPSEEK_API_KEY": ""}):
                ingest_result = run_ingest(store, directions_path, seed_path)
                draft = run_review(store, webhook_url="")

            self.assertEqual(ingest_result["stored"], 1)
            self.assertEqual(draft["status"], "draft")
            self.assertEqual(draft["selected"][0]["category"], "foreign_signal")


if __name__ == "__main__":
    unittest.main()
