import json
import tempfile
import unittest
from pathlib import Path

from aetherflux.live_rotation import (
    LiveCollectConfig,
    PlatformHealth,
    build_rotation_plan,
    classify_quality,
    hermes_decision,
    load_live_collect_config,
)


class LiveRotationTests(unittest.TestCase):
    def test_build_rotation_plan_interleaves_platforms_and_queries(self):
        config = LiveCollectConfig(
            platforms=["xiaohongshu", "douyin"],
            queries=["阳朔 旅游", "阳朔 西街"],
            target_per_platform=3,
            wait_min_seconds=90,
            wait_max_seconds=240,
        )

        plan = build_rotation_plan(config)

        self.assertEqual([task["platform"] for task in plan[:4]], ["xiaohongshu", "douyin", "xiaohongshu", "douyin"])
        self.assertEqual([task["query"] for task in plan[:4]], ["阳朔 旅游", "阳朔 旅游", "阳朔 西街", "阳朔 西街"])
        self.assertEqual([task["item_offset"] for task in plan[:4]], [0, 0, 0, 0])
        self.assertTrue(all(90 <= task["wait_after_seconds"] <= 240 for task in plan))

    def test_build_rotation_plan_advances_offset_when_query_repeats(self):
        config = LiveCollectConfig(
            platforms=["xiaohongshu"],
            queries=["阳朔 旅游"],
            target_per_platform=3,
            wait_min_seconds=90,
            wait_max_seconds=240,
        )

        plan = build_rotation_plan(config)

        self.assertEqual([task["item_offset"] for task in plan], [0, 1, 2])

    def test_build_rotation_plan_skips_paused_platforms(self):
        config = LiveCollectConfig(
            platforms=["xiaohongshu", "douyin"],
            queries=["阳朔 旅游"],
            target_per_platform=2,
            wait_min_seconds=90,
            wait_max_seconds=240,
            health={"douyin": PlatformHealth(platform="douyin", paused=True)},
        )

        plan = build_rotation_plan(config)

        self.assertEqual([task["platform"] for task in plan], ["xiaohongshu", "xiaohongshu"])

    def test_classify_quality_rejects_platform_noise_and_security_pages(self):
        bad_item = {
            "title": "用户服务协议",
            "body": "安全限制 访问链接异常 300017 我要反馈 返回首页 沪ICP备13030189号",
            "url": "https://www.xiaohongshu.com/agreements/",
            "media": {"cover_url": "data:image/png;base64,abc"},
        }

        result = classify_quality(bad_item)

        self.assertEqual(result["quality_status"], "rejected")
        self.assertIn("blocked_or_noise_page", result["reject_reason"])

    def test_classify_quality_accepts_real_visible_item(self):
        item = {
            "title": "阳朔遇龙河竹筏排队真实体验",
            "body": "今天下午遇龙河排队大约 40 分钟，价格和路线都写清楚了。",
            "url": "https://www.xiaohongshu.com/explore/abc123",
            "media": {"cover_url": "https://sns-img.example/cover.jpg"},
            "evidence": {"screenshot_path": "artifacts/live/screenshots/abc.png"},
        }

        result = classify_quality(item)

        self.assertEqual(result["quality_status"], "accepted")
        self.assertGreaterEqual(result["quality_score"], 70)

    def test_hermes_decision_pauses_only_bad_platform(self):
        health = {
            "xiaohongshu": PlatformHealth(platform="xiaohongshu", consecutive_failures=0, rejected_recent=1),
            "douyin": PlatformHealth(platform="douyin", consecutive_failures=2, rejected_recent=3),
        }

        decision = hermes_decision(health)

        self.assertEqual(decision["action"], "pause_platform")
        self.assertEqual(decision["platform"], "douyin")

    def test_load_config_from_json_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "live_collect.json"
            path.write_text(
                json.dumps(
                    {
                        "platforms": ["xiaohongshu", "douyin"],
                        "queries": ["阳朔 旅游", "阳朔 民宿"],
                        "target_per_platform": 7,
                        "wait_min_seconds": 90,
                        "wait_max_seconds": 240,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            config = load_live_collect_config(path)

        self.assertEqual(config.platforms, ["xiaohongshu", "douyin"])
        self.assertEqual(config.queries, ["阳朔 旅游", "阳朔 民宿"])
        self.assertEqual(config.target_per_platform, 7)


if __name__ == "__main__":
    unittest.main()
