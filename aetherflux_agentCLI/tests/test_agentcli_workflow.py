import json
import tempfile
import unittest
from pathlib import Path

from aetherflux_agentcli.agent_adapter import AgentCommandTemplate
from aetherflux_agentcli.bundle import BundleWriter, copy_bundle_to_inbox
from aetherflux_agentcli.cli import build_parser
from aetherflux_agentcli.safety import ActionSafety, classify_action


class AgentCLIWorkflowTests(unittest.TestCase):
    def test_bundle_writer_creates_agentcli_manifest_and_asr_jsonl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            writer = BundleWriter(root=root, mode="agentCLI", node_id="mac-local")

            bundle = writer.create_bundle(
                bundle_date="2026-05-30",
                run_id="run-agent-001",
                mission={"place": "阳朔", "industry": "旅游"},
                raw_items=[{"item_id": "dy-1", "platform": "douyin", "title": "阳朔骑行"}],
                screened_items=[{"item_id": "dy-1", "decision": "APPROVED"}],
                asr_results=[{"item_id": "dy-1", "asr_status": "success", "transcript_ref": "transcripts/dy-1.txt"}],
                agent_decisions=[{"agent": "hermes", "decision": "RETRY_WITH_ACTION"}],
                errors=[],
            )

            manifest = json.loads((bundle.path / "manifest.json").read_text(encoding="utf-8"))
            asr_lines = (bundle.path / "asr_results.jsonl").read_text(encoding="utf-8").splitlines()

            self.assertEqual(manifest["version"], "0.2.5")
            self.assertEqual(manifest["mode"], "agentCLI")
            self.assertEqual(manifest["counts"]["raw_items"], 1)
            self.assertEqual(json.loads(asr_lines[0])["transcript_ref"], "transcripts/dy-1.txt")

    def test_copy_bundle_to_main_inbox_keeps_agentcli_namespace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bundle = BundleWriter(root=root / "local", mode="agentCLI", node_id="mac-local").create_bundle(
                bundle_date="2026-05-30",
                run_id="run-agent-copy",
                mission={},
                raw_items=[],
                screened_items=[],
                asr_results=[],
                agent_decisions=[],
                errors=[],
            )

            copied = copy_bundle_to_inbox(bundle.path, root / "main-inbox")

            self.assertEqual(copied, root / "main-inbox" / "agentCLI" / "2026-05-30" / "run-agent-copy")
            self.assertTrue((copied / "agent_decisions.jsonl").exists())

    def test_safety_stops_login_captcha_account_publish_payment_delete_and_upload(self):
        blocked_actions = [
            {"action": "fill", "target": "登录密码"},
            {"action": "click", "target": "滑动验证码"},
            {"action": "click", "target": "账号设置"},
            {"action": "click", "target": "发布笔记"},
            {"action": "click", "target": "支付订单"},
            {"action": "click", "target": "删除作品"},
            {"action": "upload", "target": "private-file"},
        ]

        for action in blocked_actions:
            result = classify_action(action)
            self.assertEqual(result, ActionSafety.NEED_HUMAN)

    def test_safety_allows_bounded_public_collection_actions(self):
        for action in [
            {"action": "open", "target": "https://www.xiaohongshu.com/search_result?keyword=阳朔"},
            {"action": "scroll", "target": "results"},
            {"action": "click", "target": "展开评论"},
            {"action": "extract", "target": "visible public text"},
        ]:
            self.assertEqual(classify_action(action), ActionSafety.ALLOWED)

    def test_agent_command_template_renders_autonomous_operator_payload(self):
        template = AgentCommandTemplate(
            name="hermes",
            command=["hermes", "-z", "{payload}", "--provider", "deepseek", "--model", "deepseek-v4-pro"],
            timeout_seconds=300,
        )

        command = template.render({"role": "browser_operator", "observation": {"platform": "douyin"}})

        self.assertEqual(command[0], "hermes")
        self.assertIn('"browser_operator"', command[2])

    def test_cli_exposes_run_scheduler_and_backend_hooks(self):
        parser = build_parser()

        run = parser.parse_args(["run", "--dry-run"])
        scheduler = parser.parse_args(["scheduler-hook", "--dry-run"])
        backend = parser.parse_args(["backend-hook", "--dry-run"])

        self.assertEqual(run.command, "run")
        self.assertTrue(run.dry_run)
        self.assertEqual(scheduler.command, "scheduler-hook")
        self.assertEqual(backend.command, "backend-hook")


if __name__ == "__main__":
    unittest.main()
