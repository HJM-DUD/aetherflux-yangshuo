import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from aetherflux_shellcli.agent_adapter import AgentCommandTemplate
from aetherflux_shellcli.bundle import BundleWriter, copy_bundle_to_inbox
from aetherflux_shellcli.cli import build_parser
from aetherflux_shellcli.collector import ShellCollectionConfig, _normalize_item, _search_extract_js, commands_for_task, run_shell_collection
from aetherflux_shellcli.platforms import plan_supported_tasks


class ShellCLIWorkflowTests(unittest.TestCase):
    def test_bundle_writer_creates_manifest_and_jsonl_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            writer = BundleWriter(root=root, mode="shellCLI", node_id="mac-local")

            bundle = writer.create_bundle(
                bundle_date="2026-05-30",
                run_id="run-shell-001",
                mission={"place": "阳朔", "industry": "旅游"},
                raw_items=[
                    {
                        "item_id": "xhs-1",
                        "platform": "xiaohongshu",
                        "title": "阳朔竹筏排队",
                        "url": "https://example.test/xhs/1",
                    }
                ],
                screened_items=[{"item_id": "xhs-1", "decision": "APPROVED"}],
                asr_results=[{"item_id": "xhs-1", "asr_status": "success", "summary": "提到排队"}],
                agent_decisions=[{"item_id": "xhs-1", "agent": "hermes", "decision": "APPROVED"}],
                errors=[],
            )

            manifest = json.loads((bundle.path / "manifest.json").read_text(encoding="utf-8"))
            raw_lines = (bundle.path / "raw_items.jsonl").read_text(encoding="utf-8").splitlines()

            self.assertEqual(manifest["version"], "0.2.5")
            self.assertEqual(manifest["mode"], "shellCLI")
            self.assertEqual(manifest["bundle_date"], "2026-05-30")
            self.assertEqual(manifest["counts"]["raw_items"], 1)
            self.assertEqual(manifest["counts"]["asr_results"], 1)
            self.assertEqual(json.loads(raw_lines[0])["platform"], "xiaohongshu")
            self.assertIn("raw_items.jsonl", {file_info["relative_path"] for file_info in manifest["files"]})

    def test_copy_bundle_to_main_inbox_keeps_mode_date_and_run_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bundle = BundleWriter(root=root / "local", mode="shellCLI", node_id="mac-local").create_bundle(
                bundle_date="2026-05-30",
                run_id="run-copy-001",
                mission={},
                raw_items=[],
                screened_items=[],
                asr_results=[],
                agent_decisions=[],
                errors=[],
            )

            copied = copy_bundle_to_inbox(bundle.path, root / "main-inbox")

            self.assertEqual(copied, root / "main-inbox" / "shellCLI" / "2026-05-30" / "run-copy-001")
            self.assertTrue((copied / "manifest.json").exists())

    def test_video_channel_is_disabled_placeholder_not_planned_for_collection(self):
        tasks, errors = plan_supported_tasks(
            platforms=["xiaohongshu", "douyin", "shipinghao"],
            queries=["阳朔 旅游"],
            per_platform=1,
        )

        self.assertEqual([task["platform"] for task in tasks], ["xiaohongshu", "douyin"])
        self.assertEqual(errors[0]["platform"], "shipinghao")
        self.assertEqual(errors[0]["status"], "disabled_unsupported_v025")

    def test_agent_command_template_renders_structured_json_payload(self):
        template = AgentCommandTemplate(
            name="hermes",
            command=["hermes", "-z", "{payload}", "--provider", "deepseek", "--model", "deepseek-v4-pro"],
            timeout_seconds=300,
        )

        command = template.render({"role": "collector_supervisor", "items": [{"title": "阳朔"}]})

        self.assertEqual(command[0], "hermes")
        self.assertIn('"collector_supervisor"', command[2])
        self.assertIn("deepseek-v4-pro", command)

    def test_cli_exposes_scheduler_and_backend_hooks(self):
        parser = build_parser()

        scheduler = parser.parse_args(["scheduler-hook", "--dry-run"])
        backend = parser.parse_args(["backend-hook", "--dry-run"])

        self.assertEqual(scheduler.command, "scheduler-hook")
        self.assertTrue(scheduler.dry_run)
        self.assertEqual(backend.command, "backend-hook")
        self.assertTrue(backend.dry_run)

    def test_commands_for_task_build_real_opencli_browser_sequences(self):
        xhs = commands_for_task("xiaohongshu", "阳朔 旅游", limit=5, freshness_window_hours=24, scroll_rounds=2)
        douyin = commands_for_task("douyin", "阳朔 旅游", limit=5, freshness_window_hours=24, scroll_rounds=2)

        self.assertIn("xiaohongshu.com/search_result", " ".join(xhs[0]))
        self.assertIn("筛选", xhs[2][-1])
        self.assertIn("最新", xhs[2][-1])
        self.assertIn("一天内", xhs[2][-1])
        self.assertIn("a.title", xhs[-1][-1])
        self.assertIn("eval", xhs[-1])
        self.assertIn("open https://www.douyin.com/search/", " ".join(douyin[0]))
        self.assertIn("sort_type=2", " ".join(douyin[0]))
        self.assertIn("publish_time=1", " ".join(douyin[0]))
        self.assertIn("登录后即可搜索", douyin[2][-1])
        self.assertIn("最新发布", " ".join(command[-1] for command in douyin if command and command[0] == "opencli"))
        self.assertIn("一天内", " ".join(command[-1] for command in douyin if command and command[0] == "opencli"))
        self.assertIn("search-result-card", douyin[-1][-1])
        self.assertIn("published_at_raw", douyin[-1][-1])

    def test_douyin_extractor_handles_visible_result_cards_without_video_links(self):
        script = _search_extract_js("douyin", "阳朔 旅游", limit=5, freshness_window_hours=24, scroll_rounds=2)

        self.assertIn(".search-result-card", script)
        self.assertIn("parseDouyinCardText", script)
        self.assertIn("@", script)
        self.assertIn("·", script)
        self.assertIn("小时前", script)

    def test_normalize_rejects_navigation_and_boilerplate_rows(self):
        row = {
            "title": "首页 RED 直播 发布 消息 沪ICP备13030189号 营业执照 违法不良信息举报电话",
            "url": "https://www.xiaohongshu.com/explore?channel_type=web_search_result_notes",
        }

        item = _normalize_item("xiaohongshu", "阳朔 旅游", row)

        self.assertEqual(item["quality_status"], "rejected")
        self.assertEqual(item["reject_reason"], "navigation_or_boilerplate")

    def test_normalize_rejects_yesterday_and_one_day_ago_for_today_collection(self):
        for raw_time in ["昨天 20:49", "1天前", "2天前", "05-18", "2025-12-01", "5月22日"]:
            item = _normalize_item(
                "xiaohongshu",
                "阳朔 旅游",
                {"title": "阳朔旅游攻略", "url": "https://www.xiaohongshu.com/search_result/abc", "published_at_raw": raw_time},
            )
            self.assertEqual(item["quality_status"], "rejected")
            self.assertEqual(item["reject_reason"], "outside_today_or_24h_window")

        fresh = _normalize_item(
            "xiaohongshu",
            "阳朔 旅游",
            {"title": "阳朔旅游攻略", "url": "https://www.xiaohongshu.com/search_result/abc", "published_at_raw": "6分钟前"},
        )
        self.assertEqual(fresh["quality_status"], "accepted")

    def test_normalize_rejects_rows_without_publish_time_for_today_collection(self):
        item = _normalize_item(
            "douyin",
            "阳朔 旅游",
            {"title": "相关搜索", "url": "", "published_at_raw": ""},
        )

        self.assertEqual(item["quality_status"], "rejected")
        self.assertIn(item["reject_reason"], {"navigation_or_boilerplate", "missing_published_time"})

    def test_normalize_strips_sensitive_url_query_tokens(self):
        item = _normalize_item(
            "xiaohongshu",
            "阳朔 旅游",
            {
                "title": "阳朔旅游攻略",
                "url": "https://www.xiaohongshu.com/search_result/abc?xsec_token=secret&xsec_source=pc_search&note_id=keep",
            },
        )

        self.assertEqual(item["url"], "https://www.xiaohongshu.com/search_result/abc?note_id=keep")
        self.assertNotIn("xsec_token", json.dumps(item, ensure_ascii=False))

    def test_run_shell_collection_uses_opencli_results_and_writes_bundle(self):
        calls = []

        def fake_runner(cmd, **kwargs):
            calls.append(list(cmd))
            if cmd == ["opencli", "doctor"]:
                return subprocess.CompletedProcess(cmd, 0, stdout="Everything looks good", stderr="")
            if "eval" in cmd:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout=json.dumps(
                        [
                            {
                                "title": "阳朔遇龙河排队",
                                "author": "本地旅行者",
                                "likes": "120",
                                "published_at_raw": "1小时前",
                                "url": "https://example.test/item/1",
                            }
                        ],
                        ensure_ascii=False,
                    ),
                    stderr="",
                )
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = ShellCollectionConfig(
                platforms=["xiaohongshu", "shipinghao"],
                queries=["阳朔 旅游"],
                max_items_per_task=5,
                target_per_platform=1,
                bundle_root=root / "bundles",
                artifact_root=root / "artifacts",
                log_root=root / "logs",
            )

            result = run_shell_collection(config, runner=fake_runner, sleep_enabled=False)

            self.assertTrue(result["ok"])
            self.assertEqual(result["counts"]["raw_items"], 1)
            self.assertEqual(result["errors"][0]["platform"], "shipinghao")
            self.assertTrue((Path(result["bundle"]) / "raw_items.jsonl").exists())
            raw_line = (Path(result["bundle"]) / "raw_items.jsonl").read_text(encoding="utf-8").splitlines()[0]
            self.assertEqual(json.loads(raw_line)["title"], "阳朔遇龙河排队")
            self.assertEqual(calls[0], ["opencli", "doctor"])
            self.assertIn(["opencli", "browser", "aetherflux-shellcli-xiaohongshu", "close"], calls)

    def test_run_shell_collection_records_empty_platform_results(self):
        def fake_runner(cmd, **kwargs):
            if cmd == ["opencli", "doctor"]:
                return subprocess.CompletedProcess(cmd, 0, stdout="Everything looks good", stderr="")
            if "eval" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as temp_dir:
            config = ShellCollectionConfig(
                platforms=["douyin"],
                queries=["阳朔 旅游"],
                bundle_root=Path(temp_dir) / "bundles",
                artifact_root=Path(temp_dir) / "artifacts",
                log_root=Path(temp_dir) / "logs",
            )

            result = run_shell_collection(config, runner=fake_runner, sleep_enabled=False)

            self.assertTrue(result["ok"])
            self.assertEqual(result["counts"]["raw_items"], 0)
            self.assertEqual(result["errors"][0]["status"], "empty_result")
            self.assertEqual(result["errors"][0]["platform"], "douyin")

    def test_run_shell_collection_stops_when_opencli_doctor_fails(self):
        def fake_runner(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="Extension not connected")

        with tempfile.TemporaryDirectory() as temp_dir:
            config = ShellCollectionConfig(bundle_root=Path(temp_dir) / "bundles")

            result = run_shell_collection(config, runner=fake_runner, sleep_enabled=False)

            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "opencli_doctor_failed")
            self.assertIn("Extension", result["message"])

    def test_cli_accepts_collection_config_and_no_sleep_for_real_run(self):
        parser = build_parser()

        args = parser.parse_args(["run", "--config", "config/collect.json", "--stage", "titles", "--no-sleep"])

        self.assertEqual(args.config, "config/collect.json")
        self.assertEqual(args.stage, "titles")
        self.assertTrue(args.no_sleep)


if __name__ == "__main__":
    unittest.main()
