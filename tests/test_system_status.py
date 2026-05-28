import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aetherflux.deepseek import DeepSeekConfig
from aetherflux.cli import DEFAULT_WORKER_API_PORT
from aetherflux.server import build_advisor_connection
from aetherflux.server import build_system_status
from aetherflux.server import DEFAULT_DASHBOARD_PORT
from aetherflux.storage import IntelligenceStore


class SystemStatusTests(unittest.TestCase):
    def test_system_status_reports_latest_architecture_and_deepseek_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = IntelligenceStore(Path(temp_dir) / "intel.db")
            store.initialize()
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "local-key"}, clear=True), patch(
                "aetherflux.server.read_deepseek_status", return_value={}
            ):
                status = build_system_status(store)

        self.assertEqual(status["project"]["name_zh"], "以太通量")
        self.assertEqual(status["project"]["subproject"], "阳朔旅游情报决策系统")
        self.assertTrue(status["deepseek"]["enabled"])
        self.assertEqual(status["deepseek"]["model"], "deepseek-v4-pro")
        self.assertEqual(status["deepseek"]["connection"]["indicator"], "yellow")
        self.assertEqual(status["first_platform"]["id"], "xiaohongshu")
        self.assertEqual(status["ports"]["web"], 8788)
        self.assertEqual(status["ports"]["worker_api"], 8789)
        self.assertEqual(DEFAULT_DASHBOARD_PORT, 8788)
        self.assertEqual(DEFAULT_WORKER_API_PORT, 8789)
        self.assertEqual(status["storage"]["mode"], "local_sqlite")
        self.assertEqual(status["storage"]["evidence_retention_hours"], 48)
        self.assertIn("xiaohongshu", status["collector"]["platforms"])
        self.assertIn("douyin", status["collector"]["platforms"])
        self.assertIn("wechat_channels", status["collector"]["platforms"])
        self.assertIn("cross_verification", status["modules"])
        self.assertIn("geo_risk", status["modules"])
        self.assertIn("bilingual_display", status["modules"])

    def test_advisor_connection_indicator_states(self):
        disabled = build_advisor_connection(DeepSeekConfig())
        self.assertEqual(disabled["indicator"], "red")

        config = DeepSeekConfig(api_key="local-key", model="deepseek-v4-pro")
        with patch("aetherflux.server.read_deepseek_status", return_value={}):
            unverified = build_advisor_connection(config)
        self.assertEqual(unverified["indicator"], "yellow")

        with patch(
            "aetherflux.server.read_deepseek_status",
            return_value={"state": "connected", "model": "deepseek-v4-pro", "replied_at": "2026-05-20T00:00:00Z"},
        ):
            connected = build_advisor_connection(config)
        self.assertEqual(connected["indicator"], "green")


if __name__ == "__main__":
    unittest.main()
