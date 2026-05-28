import tempfile
import unittest
from pathlib import Path

from aetherflux.collector_model import (
    build_daily_bundle_manifest,
    make_hard_dedupe_key,
    make_topic_cluster_key,
    plan_keyframe_offsets,
    select_comment_samples,
)
from aetherflux.storage import IntelligenceStore


class V02CollectorModelTests(unittest.TestCase):
    def test_hard_dedupe_only_collapses_exact_platform_identity(self):
        first = {
            "platform": "xiaohongshu",
            "url": "https://xhs.example/note/123?share=abc",
            "title": "阳朔遇龙河排队",
            "body": "今天很多人说排队。",
            "author": "user-a",
        }
        same_url = {
            "platform": "xiaohongshu",
            "url": "https://xhs.example/note/123?share=xyz",
            "title": "阳朔遇龙河排队",
            "body": "另一个入口采到同一条。",
            "author": "user-a",
        }
        same_topic_different_user = {
            "platform": "xiaohongshu",
            "url": "https://xhs.example/note/999",
            "title": "阳朔遇龙河排队",
            "body": "今天很多人说排队。",
            "author": "user-b",
        }

        self.assertEqual(make_hard_dedupe_key(first), make_hard_dedupe_key(same_url))
        self.assertNotEqual(make_hard_dedupe_key(first), make_hard_dedupe_key(same_topic_different_user))
        self.assertEqual(make_topic_cluster_key(first), make_topic_cluster_key(same_topic_different_user))

    def test_video_keyframes_include_start_middle_end_and_interval_points(self):
        self.assertEqual(plan_keyframe_offsets(45), [0, 22, 45])
        self.assertEqual(plan_keyframe_offsets(75), [0, 15, 30, 37, 45, 60, 75])

    def test_comment_sampling_preserves_hot_recent_author_and_keyword_comments(self):
        comments = []
        for index in range(40):
            comments.append(
                {
                    "id": f"c{index}",
                    "text": f"普通评论 {index}",
                    "likes": index,
                    "published_at": f"2026-05-20T00:{index:02d}:00Z",
                    "is_author_reply": False,
                }
            )
        comments.append({"id": "risk", "text": "停车太贵像宰客", "likes": 0, "published_at": "2026-05-20T01:00:00Z"})
        comments.append({"id": "author", "text": "作者补充路线", "likes": 0, "published_at": "2026-05-20T01:01:00Z", "is_author_reply": True})

        selected = select_comment_samples(comments, hot_limit=3, recent_limit=3, keywords=["宰客", "排队"])
        selected_ids = {comment["id"] for comment in selected}

        self.assertIn("c39", selected_ids)
        self.assertIn("c0", selected_ids)
        self.assertIn("risk", selected_ids)
        self.assertIn("author", selected_ids)

    def test_official_sources_require_review_after_mission_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = IntelligenceStore(Path(temp_dir) / "aetherflux.db")
            store.initialize()
            store.upsert_mission("m-yangshuo", "阳朔", "旅游", ["景区"])
            store.upsert_official_source("src-1", "m-yangshuo", "https://yangshuo.example.gov.cn", "阳朔文旅")

            self.assertEqual(store.list_official_sources("m-yangshuo")[0]["status"], "active")

            store.upsert_mission("m-yangshuo", "武汉", "旅游", ["景区"])

            self.assertEqual(store.list_official_sources("m-yangshuo")[0]["status"], "needs_review")

    def test_retention_and_daily_bundle_metadata_are_local_first(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = IntelligenceStore(root / "aetherflux.db")
            store.initialize()
            store.set_retention_hours(72)
            store.record_cloud_log_sync("sync-2026-02", "cleanup", "succeeded", {"log_month": "2026-02"})
            store.record_cloud_log_sync("sync-2026-05", "upload", "succeeded", {"log_month": "2026-05"})
            store.save_daily_bundle(
                {
                    "id": "bundle-2026-05-28",
                    "bundle_date": "2026-05-28",
                    "node_id": "mac-local",
                    "path": str(root / "daily_bundle_2026-05-28"),
                    "sha256": "abc123",
                    "size_bytes": 2048,
                    "manifest_json": {"items": 10},
                    "cloud_log_status": "pending",
                }
            )

            manifest = build_daily_bundle_manifest(
                bundle_date="2026-05-28",
                node_id="mac-local",
                counts={"raw_items": 10, "comments": 30},
                files=[{"path": "raw_items.jsonl", "sha256": "abc"}],
                errors=[],
            )

            self.assertEqual(store.get_retention_hours(), 72)
            self.assertEqual(store.get_cloud_log_months(), 3)
            self.assertEqual(store.list_daily_bundles()[0]["sha256"], "abc123")
            self.assertEqual(len(store.list_cloud_log_syncs()), 2)
            self.assertEqual(manifest["counts"]["comments"], 30)
            self.assertEqual(manifest["contains_raw_media"], False)


if __name__ == "__main__":
    unittest.main()
