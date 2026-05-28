import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from aetherflux.xhs import (
    DEFAULT_QUERY_CLUSTERS,
    JSONFeedXHSDriver,
    XHSState,
    collect_xhs,
    dedupe_raw_items,
    filter_by_window,
)


NOW = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)


class XHSCollectorTests(unittest.TestCase):
    def test_query_clusters_cover_yangshuo_tourism_topics(self):
        cluster_ids = {cluster["id"] for cluster in DEFAULT_QUERY_CLUSTERS}

        self.assertEqual(len(DEFAULT_QUERY_CLUSTERS), 10)
        self.assertIn("scenic_routes", cluster_ids)
        self.assertIn("bamboo_rafting", cluster_ids)
        self.assertIn("cycling_hiking", cluster_ids)
        self.assertIn("hotels_homestays", cluster_ids)
        self.assertIn("food_nightlife", cluster_ids)
        self.assertIn("family_couples", cluster_ids)
        self.assertIn("photo_shooting", cluster_ids)
        self.assertIn("rain_traffic", cluster_ids)
        self.assertIn("complaints_risks", cluster_ids)
        self.assertIn("foreign_view", cluster_ids)
        self.assertTrue(all(cluster["queries"] for cluster in DEFAULT_QUERY_CLUSTERS))

    def test_backfill_window_keeps_only_recent_seven_days(self):
        items = [
            {"title": "today", "published_at": "2026-05-20T08:00:00Z"},
            {"title": "seven days ago", "published_at": "2026-05-13T12:00:00Z"},
            {"title": "too old", "published_at": "2026-05-12T11:59:59Z"},
        ]

        kept = filter_by_window(items, start_at=NOW.replace(day=13), watermark=None)

        self.assertEqual([item["title"] for item in kept], ["today", "seven days ago"])

    def test_daily_window_keeps_only_items_newer_than_watermark(self):
        items = [
            {"title": "new", "published_at": "2026-05-20T08:00:00Z"},
            {"title": "same", "published_at": "2026-05-19T10:00:00Z"},
            {"title": "old", "published_at": "2026-05-18T10:00:00Z"},
        ]

        kept = filter_by_window(items, start_at=None, watermark="2026-05-19T10:00:00Z")

        self.assertEqual([item["title"] for item in kept], ["new"])

    def test_daily_collection_keeps_today_only_when_watermark_is_old(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.json"
            output_path = root / "raw.json"
            state_path = root / "state.json"
            state_path.write_text(
                json.dumps({"watermark_published_at": "2026-05-18T10:00:00Z"}, ensure_ascii=False),
                encoding="utf-8",
            )
            source_path.write_text(
                json.dumps(
                    [
                        {
                            "title": "今日阳朔骑行",
                            "body": "十里画廊路线更新",
                            "url": "https://xhs.example/note/today",
                            "published_at": "2026-05-20T08:00:00Z",
                            "query": "阳朔 骑行",
                        },
                        {
                            "title": "中国时间昨日阳朔骑行",
                            "body": "昨天的路线",
                            "url": "https://xhs.example/note/yesterday",
                            "published_at": "2026-05-19T15:00:00Z",
                            "query": "阳朔 骑行",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            collect_xhs(
                driver=JSONFeedXHSDriver(source_path),
                mode="daily",
                state_path=state_path,
                output_path=output_path,
                now=NOW,
            )

            saved_items = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual([item["title"] for item in saved_items], ["今日阳朔骑行"])

    def test_dedupe_prefers_note_url_then_content_hash(self):
        items = [
            {"title": "遇龙河排队", "body": "票务指引不清楚", "url": "https://xhs.example/note/1"},
            {"title": "遇龙河排队", "body": "另一个查询命中", "url": "https://xhs.example/note/1"},
            {"title": "西街夜游", "body": "安静路线", "url": ""},
            {"title": "西街夜游", "body": "安静路线", "url": ""},
        ]

        deduped = dedupe_raw_items(items)

        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["title"], "遇龙河排队")
        self.assertEqual(deduped[1]["title"], "西街夜游")

    def test_collect_persists_success_state_and_watermark(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.json"
            output_path = root / "raw.json"
            state_path = root / "state.json"
            source_path.write_text(
                json.dumps(
                    [
                        {
                            "title": "阳朔西街夜生活",
                            "body": "游客关注安静路线",
                            "url": "https://xhs.example/note/new",
                            "published_at": "2026-05-20T09:00:00Z",
                            "query": "阳朔 西街 夜生活",
                        },
                        {
                            "title": "阳朔老攻略",
                            "body": "超过七天",
                            "url": "https://xhs.example/note/old",
                            "published_at": "2026-05-01T09:00:00Z",
                            "query": "阳朔 西街 夜生活",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = collect_xhs(
                driver=JSONFeedXHSDriver(source_path),
                mode="backfill",
                state_path=state_path,
                output_path=output_path,
                days=7,
                now=NOW,
            )

            saved_items = json.loads(output_path.read_text(encoding="utf-8"))
            saved_state = XHSState.load(state_path)
            self.assertEqual(result["stored"], 1)
            self.assertEqual(saved_items[0]["platform"], "xiaohongshu")
            self.assertEqual(saved_items[0]["query"], "阳朔 西街 夜生活")
            self.assertEqual(saved_state.watermark_published_at, "2026-05-20T09:00:00Z")
            self.assertEqual(saved_state.last_error, "")
            self.assertIn("food_nightlife", saved_state.last_query_clusters)


if __name__ == "__main__":
    unittest.main()
