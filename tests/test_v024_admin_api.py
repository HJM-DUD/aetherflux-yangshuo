import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from aetherflux.admin_api import create_app
from aetherflux.storage import IntelligenceStore


class V024AdminApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store = IntelligenceStore(self.root / "aetherflux.db")
        self.store.initialize()
        self.client = TestClient(create_app(self.store, project_root=self.root))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dashboard_summary_uses_v1_api_and_never_exposes_secrets(self):
        self.store.upsert_candidate(
            {
                "id": "c1",
                "title": "阳朔竹筏排队升温",
                "summary": "小红书出现多条排队讨论",
                "platform": "xiaohongshu",
                "source": "seed",
                "score": 88,
                "signals": ["风险预警"],
                "geo_risk": {"probability": 0.6, "level": "medium", "reasons": ["同质标题"]},
            }
        )
        self.store.set_human_decision("c1", "approved")

        response = self.client.get("/api/v1/dashboard/summary")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], "V0.2.4")
        self.assertEqual(payload["counts"]["candidates"], 1)
        self.assertEqual(payload["counts"]["approved"], 1)
        dumped = json.dumps(payload, ensure_ascii=False).lower()
        self.assertNotIn("api_key", dumped)
        self.assertNotIn("cookie", dumped)
        self.assertNotIn("token", dumped)

    def test_collection_config_reads_defaults_when_file_absent(self):
        """Without config/live_collect.json in temp dir, GET returns filled defaults."""
        response = self.client.get("/api/v1/collection/config")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["platforms"], ["xiaohongshu", "douyin"])
        self.assertIn("manual_queries", payload)
        self.assertIsInstance(payload["manual_queries"], list)

    def test_collection_config_writes_to_file_and_sqlite(self):
        """PUT writes config/live_collect.json and SQLite; GET reads it back."""
        config_file = self.root / "config" / "live_collect.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps(
                {
                    "query_strategy": "hybrid",
                    "scroll_stop_after_no_new_rounds": 2,
                    "max_items_per_task": 20,
                    "detail_limit_per_task": 1,
                    "video_processing_priority": "asr",
                    "enable_keyframes": False,
                    "asr_backend": "auto",
                    "asr_model": "small",
                    "asr_language": "zh",
                    "quality_goal": "v023_asr_first_title_pool",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        update = {
            "platforms": ["xiaohongshu", "douyin"],
            "manual_queries": ["阳朔 旅游", "阳朔 竹筏"],
            "segments": ["景区", "民宿"],
            "risk_terms": ["避雷"],
            "opportunity_terms": ["攻略"],
            "hermes_queries": ["阳朔 新玩法"],
            "query_strategy": "hybrid",
            "target_per_platform": 180,
            "title_target_per_platform": 180,
            "deep_process_limit_per_platform": 36,
            "freshness_window_hours": 24,
            "scroll_rounds_per_query": 6,
            "scroll_stop_after_no_new_rounds": 2,
            "wait_min_seconds": 20,
            "wait_max_seconds": 55,
            "max_items_per_task": 20,
            "detail_limit_per_task": 1,
            "video_processing_priority": "asr",
            "enable_keyframes": False,
            "asr_backend": "auto",
            "asr_model": "small",
            "asr_language": "zh",
            "cooldown_minutes_on_limit": 45,
            "quality_goal": "v023_asr_first_title_pool",
            "parallel_limit": 3,
        }

        saved = self.client.put("/api/v1/collection/config", json=update)
        self.assertEqual(saved.status_code, 200)

        # Verify file was written
        self.assertTrue(config_file.exists())
        written = json.loads(config_file.read_text(encoding="utf-8"))
        self.assertEqual(written["asr_backend"], "auto")
        self.assertEqual(written["max_items_per_task"], 20)

        # Verify GET returns updated values
        loaded = self.client.get("/api/v1/collection/config")
        self.assertEqual(loaded.status_code, 200)
        self.assertEqual(loaded.json()["parallel_limit"], 3)
        self.assertEqual(loaded.json()["manual_queries"], ["阳朔 旅游", "阳朔 竹筏"])

    def test_collection_jobs_are_recorded_with_local_log_paths(self):
        response = self.client.post(
            "/api/v1/collection/jobs",
            json={"platform": "xiaohongshu", "stage": "titles", "dry_run": True},
        )

        self.assertEqual(response.status_code, 200)
        job = response.json()
        self.assertEqual(job["platform"], "xiaohongshu")
        self.assertEqual(job["stage"], "titles")
        self.assertIn(job["status"], ["queued", "running", "succeeded"])
        self.assertTrue(job["log_path"].endswith(".log"))
        self.assertNotIn("cookie", json.dumps(job).lower())

    def test_collection_job_detail_and_log_endpoints(self):
        """GET /api/v1/collection/jobs/{id} returns job; /log returns log content."""
        create = self.client.post(
            "/api/v1/collection/jobs",
            json={"platform": "douyin", "stage": "screen", "dry_run": True},
        )
        self.assertEqual(create.status_code, 200)
        job_id = create.json()["id"]

        detail = self.client.get(f"/api/v1/collection/jobs/{job_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], job_id)

        log_resp = self.client.get(f"/api/v1/collection/jobs/{job_id}/log")
        self.assertEqual(log_resp.status_code, 200)

    def test_collection_job_not_found_returns_404(self):
        response = self.client.get("/api/v1/collection/jobs/nonexistent-job-id")
        self.assertEqual(response.status_code, 404)

    def test_system_diagnose_returns_deepseek_error_without_500(self):
        with patch("aetherflux.admin_api.run_deepseek_smoke_test", side_effect=RuntimeError("ssl failed")):
            response = self.client.get("/api/v1/system/diagnose")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("deepseek", payload)
        self.assertFalse(payload["deepseek"]["ok"])
        self.assertIn("opencli", payload)
        self.assertIn("runtime", payload)

    def test_collection_job_cancel_marks_queued_job_cancelled(self):
        self.store.save_admin_job(
            {
                "id": "queued-cancel-test",
                "platform": "xiaohongshu",
                "stage": "titles",
                "status": "queued",
                "dry_run": False,
                "command": ["python", "-m", "aetherflux.cli", "opencli-rotate"],
                "log_path": str(self.root / "logs" / "admin" / "queued-cancel-test.log"),
                "created_at": "2026-05-29T00:00:00Z",
            }
        )

        response = self.client.post("/api/v1/collection/jobs/queued-cancel-test/cancel")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["cancelled"])
        self.assertEqual(payload["job"]["status"], "cancelled")
        self.assertFalse(payload["job"].get("physical_delete_performed", False))

    def test_title_pool_returns_empty_when_artifact_dir_missing(self):
        response = self.client.get("/api/v1/title-pool")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["empty_reason"], "artifact_dir_missing")

    def test_video_processing_returns_empty_when_artifact_dir_missing(self):
        response = self.client.get("/api/v1/video-processing")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["empty_reason"], "artifact_dir_missing")

    def test_soft_delete_trash_can_restore_and_mark_items_cleanable(self):
        self.store.upsert_candidate(
            {
                "id": "trash-candidate",
                "title": "临时排除标题",
                "summary": "进入回收站后可以恢复",
                "platform": "douyin",
                "source": "seed",
                "score": 42,
            }
        )

        moved = self.client.post(
            "/api/v1/trash",
            json={"item_type": "candidate", "ids": ["trash-candidate"], "reason": "人工多选排除"},
        )
        trashed = self.client.get("/api/v1/trash")
        restored = self.client.post("/api/v1/trash/restore", json={"ids": ["trash-candidate"]})
        cleanable = self.client.post("/api/v1/trash/mark-cleanable")

        self.assertEqual(moved.status_code, 200)
        self.assertEqual(moved.json()["moved"], 1)
        self.assertEqual(trashed.json()["items"][0]["id"], "trash-candidate")
        self.assertEqual(restored.json()["restored"], 1)
        self.assertEqual(cleanable.status_code, 200)
        self.assertIn("physical_delete_performed", cleanable.json())
        self.assertFalse(cleanable.json()["physical_delete_performed"])


if __name__ == "__main__":
    unittest.main()
