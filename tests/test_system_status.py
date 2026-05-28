import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aetherflux.server import build_system_status
from aetherflux.storage import IntelligenceStore


class SystemStatusTests(unittest.TestCase):
    def test_system_status_reports_latest_architecture_and_deepseek_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = IntelligenceStore(Path(temp_dir) / "intel.db")
            store.initialize()
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "local-key"}, clear=True):
                status = build_system_status(store)

        self.assertEqual(status["project"]["name_zh"], "以太通量")
        self.assertEqual(status["project"]["subproject"], "阳朔旅游情报决策系统")
        self.assertTrue(status["deepseek"]["enabled"])
        self.assertEqual(status["deepseek"]["model"], "deepseek-v4-pro")
        self.assertEqual(status["first_platform"]["id"], "xiaohongshu")
        self.assertIn("cross_verification", status["modules"])
        self.assertIn("geo_risk", status["modules"])
        self.assertIn("bilingual_display", status["modules"])


if __name__ == "__main__":
    unittest.main()
