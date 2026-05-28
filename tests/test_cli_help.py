import subprocess
import sys
import unittest


class CLIHelpTests(unittest.TestCase):
    def test_cli_help_marks_current_ingest_as_local_json_feed(self):
        result = subprocess.run(
            [sys.executable, "-m", "aetherflux.cli", "ingest", "--help"],
            check=True,
            capture_output=True,
            text=True,
        )

        output = " ".join(result.stdout.split())
        self.assertIn("local JSON feed", output)
        self.assertIn("not live platform crawling", output)

    def test_xhs_help_marks_current_driver_as_json_feed_not_live_crawler(self):
        result = subprocess.run(
            [sys.executable, "-m", "aetherflux.cli", "xhs", "backfill", "--help"],
            check=True,
            capture_output=True,
            text=True,
        )

        output = " ".join(result.stdout.split())
        self.assertIn("JSON feed", output)
        self.assertIn("not a live Xiaohongshu crawler", output)

    def test_live_help_exposes_xiaohongshu_and_douyin_only(self):
        result = subprocess.run(
            [sys.executable, "-m", "aetherflux.cli", "live", "--help"],
            check=True,
            capture_output=True,
            text=True,
        )

        output = " ".join(result.stdout.split())
        self.assertIn("xiaohongshu", output)
        self.assertIn("douyin", output)
        self.assertNotIn("wechat_channels", output)


if __name__ == "__main__":
    unittest.main()
