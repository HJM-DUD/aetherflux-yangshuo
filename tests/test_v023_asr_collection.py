import json
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from aetherflux.asr_pipeline import ASRConfig, dependency_status, process_video_item, select_asr_backend
from aetherflux.freshness import evaluate_freshness
from aetherflux.live_rotation import load_live_collect_config
from aetherflux.query_planner import build_hybrid_queries


class V023ASRCollectionTests(unittest.TestCase):
    def test_freshness_accepts_recent_24_hour_terms(self):
        now = datetime(2026, 5, 29, 12, 0)

        recent = evaluate_freshness("3小时前", now=now, window_hours=24)
        stale = evaluate_freshness("2026年5月27日", now=now, window_hours=24)

        self.assertEqual(recent.status, "recent")
        self.assertEqual(stale.status, "stale")

    def test_hybrid_query_planner_expands_manual_queries_with_segments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            directions = Path(tmpdir) / "directions.json"
            directions.write_text(json.dumps({"places": ["阳朔", "遇龙河"]}, ensure_ascii=False), encoding="utf-8")
            rows = build_hybrid_queries({"manual_queries": ["阳朔 旅游"], "segments": ["民宿"], "hermes_queries": ["阳朔 新开业"]}, directions)

        queries = [row.query for row in rows]
        self.assertIn("阳朔 旅游", queries)
        self.assertIn("阳朔 民宿", queries)
        self.assertIn("阳朔 新开业", queries)

    def test_live_config_loads_v023_asr_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "live_collect.json"
            config_path.write_text(
                json.dumps(
                    {
                        "platforms": ["xiaohongshu", "douyin"],
                        "manual_queries": ["阳朔 旅游"],
                        "query_strategy": "hybrid",
                        "freshness_window_hours": 24,
                        "title_target_per_platform": 200,
                        "deep_process_limit_per_platform": 40,
                        "video_processing_priority": "asr",
                        "enable_keyframes": False,
                        "asr_backend": "auto",
                        "asr_model": "small",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = load_live_collect_config(config_path)

        self.assertEqual(config.freshness_window_hours, 24)
        self.assertEqual(config.title_target_per_platform, 200)
        self.assertEqual(config.deep_process_limit_per_platform, 40)
        self.assertEqual(config.video_processing_priority, "asr")
        self.assertFalse(config.enable_keyframes)
        self.assertGreater(len(config.queries), 1)

    def test_asr_dependency_status_is_explicit(self):
        status = dependency_status()

        self.assertIn("ffmpeg", status)
        self.assertIn("faster_whisper", status)
        self.assertIn(select_asr_backend("auto"), {"", "mlx_whisper", "faster_whisper", "whisper"})

    def test_video_processing_reports_missing_media_without_fake_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = process_video_item(
                {"platform": "douyin", "title": "阳朔视频", "url": "https://www.douyin.com/video/1"},
                tmpdir,
                config=ASRConfig(),
                runner=lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
            )

        self.assertEqual(result["deep_process_status"], "failed")
        self.assertEqual(result["asr_status"], "failed")
        self.assertEqual(result["error"], "video_download_not_available")


if __name__ == "__main__":
    unittest.main()
