import os
import stat
import subprocess
import unittest
from pathlib import Path


SCRIPT = Path("scripts/hermes_collect_live.sh")
OPENCLI_SCRIPT = Path("scripts/hermes_collect_opencli.sh")


class HermesCollectLiveScriptTests(unittest.TestCase):
    def test_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.exists())
        mode = SCRIPT.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)
        self.assertTrue(OPENCLI_SCRIPT.exists())
        self.assertTrue(OPENCLI_SCRIPT.stat().st_mode & stat.S_IXUSR)

    def test_script_exposes_hermes_live_collection_controls(self):
        content = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("AETHERFLUX_COLLECT_BACKEND", content)
        self.assertIn("scripts/hermes_collect_opencli.sh", content)
        self.assertIn("live-rotate", content)

    def test_opencli_script_exposes_opencli_controls(self):
        content = OPENCLI_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("AETHERFLUX_LIVE_CONFIG", content)
        self.assertIn("opencli doctor", content)
        self.assertIn("python3 -m aetherflux.cli opencli-rotate", content)
        self.assertIn("AETHERFLUX_DRY_RUN", content)
        self.assertIn("AETHERFLUX_OPENCLI_STAGE", content)
        self.assertIn("AETHERFLUX_HERMES_SCREEN", content)
        self.assertIn("--stage", content)

    def test_script_does_not_use_forbidden_batch_delete_commands(self):
        content = SCRIPT.read_text(encoding="utf-8") + OPENCLI_SCRIPT.read_text(encoding="utf-8")

        forbidden_fragments = ["rm -rf", "rmdir /s", "rd /s", "del /s", "Remove-Item -Recurse"]
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, content)

    def test_dry_run_prints_planned_platform_query_commands(self):
        env = os.environ.copy()
        env.update(
            {
                "AETHERFLUX_DRY_RUN": "1",
                "AETHERFLUX_LIVE_PLATFORMS": "xiaohongshu,douyin",
                "AETHERFLUX_LIVE_QUERIES": "阳朔 旅游;阳朔 西街",
                "AETHERFLUX_TARGET_PER_PLATFORM": "2",
                "AETHERFLUX_OUTPUT_DIR": "artifacts/test-live",
                "AETHERFLUX_LOG_DIR": "logs/test-live",
            }
        )

        result = subprocess.run(
            [str(SCRIPT)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

        self.assertIn("dry_run", result.stdout)
        self.assertIn("opencli_rotate_plan", result.stdout)
        self.assertIn("xiaohongshu", result.stdout)
        self.assertIn("douyin", result.stdout)
        self.assertIn("阳朔 旅游", result.stdout)
        self.assertIn("阳朔 西街", result.stdout)


if __name__ == "__main__":
    unittest.main()
