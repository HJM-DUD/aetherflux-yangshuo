import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from aetherflux.opencli_collectors import (
    OpenCLIResult,
    commands_for_task,
    map_opencli_error,
    normalize_opencli_items,
    run_opencli_command,
    run_opencli_sequence,
    run_opencli_rotation,
    screen_title_pool,
    command_for_task,
)


class OpenCLICollectorsTests(unittest.TestCase):
    def test_normalizes_xiaohongshu_search_rows_to_raw_items(self):
        rows = [
            {
                "rank": 1,
                "title": "阳朔遇龙河竹筏体验",
                "author": "本地旅行者",
                "likes": "1.2万",
                "published_at": "1小时前",
                "url": "https://www.xiaohongshu.com/search_result/abc",
            }
        ]

        items = normalize_opencli_items("xiaohongshu", "search", "阳朔 旅游", rows)

        self.assertEqual(items[0]["platform"], "xiaohongshu")
        self.assertEqual(items[0]["title"], "阳朔遇龙河竹筏体验")
        self.assertEqual(items[0]["author"], "本地旅行者")
        self.assertEqual(items[0]["engagement"]["likes"], 12000)
        self.assertEqual(items[0]["published_at_raw"], "1小时前")
        self.assertEqual(items[0]["freshness_status"], "recent")
        self.assertEqual(items[0]["capture_method"], "opencli_browser_bridge")
        self.assertEqual(items[0]["quality_status"], "accepted")

    def test_normalizes_douyin_hashtag_rows_to_signal_items(self):
        rows = [{"name": "阳朔旅行", "id": "123", "view_count": 980000}]

        items = normalize_opencli_items("douyin", "hashtag", "阳朔", rows)

        self.assertEqual(items[0]["platform"], "douyin")
        self.assertEqual(items[0]["signal_type"], "hashtag")
        self.assertEqual(items[0]["title"], "阳朔旅行")
        self.assertEqual(items[0]["engagement"]["views"], 980000)

    def test_normalizes_douyin_jingxuan_search_rows_to_video_items(self):
        rows = [{"title": "阳朔骑行路线", "body": "遇龙河骑行很热", "url": "https://www.douyin.com/video/123"}]

        items = normalize_opencli_items("douyin", "jingxuan_search", "阳朔 骑行", rows)

        self.assertEqual(items[0]["platform"], "douyin")
        self.assertEqual(items[0]["signal_type"], "search_result_visible")
        self.assertEqual(items[0]["content_type"], "video")
        self.assertEqual(items[0]["url"], "https://www.douyin.com/video/123")
        self.assertEqual(items[0]["evidence"]["entry_url"], "https://www.douyin.com/jingxuan")
        self.assertEqual(items[0]["evidence"]["search_query"], "阳朔 骑行")

    def test_maps_opencli_errors_to_health_codes(self):
        self.assertEqual(map_opencli_error("AuthRequiredError: login required"), "auth_required")
        self.assertEqual(map_opencli_error("SECURITY_BLOCK Xiaohongshu security block"), "security_block")
        self.assertEqual(map_opencli_error("EmptyResultError no rows"), "empty_result")
        self.assertEqual(map_opencli_error("some stack trace"), "command_failed")

    def test_run_opencli_command_parses_json_stdout(self):
        def fake_runner(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps([{"title": "阳朔"}]), stderr="")

        result = run_opencli_command(["opencli", "xiaohongshu", "search", "阳朔", "-f", "json"], runner=fake_runner)

        self.assertTrue(result.ok)
        self.assertEqual(result.rows, [{"title": "阳朔"}])

    def test_run_opencli_sequence_parses_last_command_stdout(self):
        def fake_runner(cmd, **kwargs):
            if "eval" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps([{"title": "阳朔抖音"}]), stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="Waited 3s", stderr="")

        result = run_opencli_sequence(commands_for_task("douyin", "阳朔", limit=2), runner=fake_runner)

        self.assertTrue(result.ok)
        self.assertEqual(result.rows, [{"title": "阳朔抖音"}])

    def test_run_opencli_rotation_dry_run_interleaves_platforms(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / "live_collect.json"
            config.write_text(
                json.dumps(
                    {
                        "platforms": ["xiaohongshu", "douyin"],
                        "queries": ["阳朔 旅游", "阳朔 西街"],
                        "target_per_platform": 2,
                        "wait_min_seconds": 90,
                        "wait_max_seconds": 240,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = run_opencli_rotation(config_path=config, dry_run=True)

        self.assertEqual(result["event"], "opencli_rotate_plan")
        self.assertEqual([task["platform"] for task in result["tasks"][:4]], ["xiaohongshu", "douyin", "xiaohongshu", "douyin"])

    def test_command_for_task_uses_configured_limit(self):
        command = command_for_task("xiaohongshu", "阳朔 旅游", limit=5)

        self.assertIn("--limit", command)
        self.assertIn("5", command)

    def test_douyin_command_uses_jingxuan_not_creator_adapter(self):
        command = command_for_task("douyin", "阳朔 旅游", limit=5)
        command_text = " ".join(command)

        self.assertIn("browser", command)
        self.assertIn("https://www.douyin.com/jingxuan", command)
        self.assertNotIn("creator.douyin.com", command_text)
        self.assertNotIn("hashtag", command_text)

    def test_douyin_task_opens_jingxuan_then_searches_query_before_extracting_results(self):
        commands = commands_for_task("douyin", "阳朔 旅游", limit=5)
        command_texts = [" ".join(command) for command in commands]

        self.assertIn("open https://www.douyin.com/jingxuan", command_texts[0])
        self.assertIn("wait time 3", command_texts[1])
        self.assertIn('fill input[placeholder*="搜索"] 阳朔 旅游', command_texts[2])
        self.assertIn("keys Enter", command_texts[3])
        self.assertIn("wait time 5", command_texts[4])
        self.assertIn("eval", command_texts[5])
        self.assertIn("wait time 2", command_texts[6])
        self.assertIn("eval", command_texts[7])

    def test_xiaohongshu_task_uses_browser_search_filter_and_scroll_extractor(self):
        commands = commands_for_task("xiaohongshu", "阳朔 旅游", limit=5)
        command_texts = [" ".join(command) for command in commands]

        self.assertIn("browser aetherflux-xiaohongshu", command_texts[0])
        self.assertIn("xiaohongshu.com/search_result", command_texts[0])
        self.assertIn("eval", command_texts[2])
        self.assertIn("最新", command_texts[2])
        self.assertIn("eval", command_texts[-1])
        self.assertIn("scrollRounds", command_texts[-1])

    def test_stale_items_are_rejected_by_freshness_gate(self):
        rows = [{"title": "阳朔旧攻略", "body": "这是一条足够长的旧内容", "url": "https://www.douyin.com/video/1", "published_at_raw": "2020年1月1日"}]

        items = normalize_opencli_items("douyin", "jingxuan_search", "阳朔", rows)

        self.assertEqual(items[0]["freshness_status"], "stale")
        self.assertEqual(items[0]["quality_status"], "rejected")
        self.assertIn("outside_freshness_window", items[0]["reject_reason"])

    def test_screen_title_pool_prefers_risk_and_opportunity_items(self):
        items = [
            {"platform": "douyin", "title": "阳朔普通视频", "body": "普通内容足够长", "quality_status": "accepted", "quality_score": 70},
            {"platform": "douyin", "title": "阳朔避雷攻略", "body": "排队和价格问题，路线也讲清楚", "quality_status": "accepted", "quality_score": 70},
        ]

        screened = screen_title_pool(items, per_platform_limit=1)

        self.assertEqual(screened[0]["title"], "阳朔避雷攻略")
        self.assertEqual(screened[0]["deep_process_status"], "selected_for_asr")
        self.assertIn("risk", screened[0]["decision_hints"])

    def test_run_opencli_rotation_stops_when_doctor_fails(self):
        doctor = OpenCLIResult(ok=False, rows=[], stdout="", stderr="Extension: not connected", returncode=1)

        result = run_opencli_rotation(dry_run=False, doctor_result=doctor)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "opencli_doctor_failed")
        self.assertIn("Extension", result["message"])


if __name__ == "__main__":
    unittest.main()
