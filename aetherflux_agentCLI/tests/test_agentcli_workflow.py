import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aetherflux_agentcli.agent_adapter import AgentCommandTemplate
from aetherflux_agentcli.bundle import BundleWriter, copy_bundle_to_inbox
from aetherflux_agentcli.cli import build_parser
from aetherflux_agentcli.collector import AgentCollectionConfig, _parse_agent_decision, commands_for_task, run_agent_collection
from aetherflux_agentcli.media_asr import ASRConfig, classify_information_value, dependency_status, process_video_item, select_asr_backend
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

            self.assertEqual(manifest["version"], "0.2.7")
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

    def test_agent_decision_parser_accepts_json_code_block(self):
        parsed = _parse_agent_decision(
            '```json\n{"decision":"APPROVED","reason":"继续","action_payload":{"action":"open","target":"douyin"}}\n```'
        )

        self.assertEqual(parsed["decision"], "APPROVED")

    def test_cli_exposes_run_scheduler_and_backend_hooks(self):
        parser = build_parser()

        run = parser.parse_args(["run", "--dry-run"])
        scheduler = parser.parse_args(["scheduler-hook", "--dry-run"])
        backend = parser.parse_args(["backend-hook", "--dry-run"])

        self.assertEqual(run.command, "run")
        self.assertTrue(run.dry_run)
        self.assertEqual(scheduler.command, "scheduler-hook")
        self.assertEqual(backend.command, "backend-hook")

    def test_agent_collector_builds_recent_filtered_opencli_commands(self):
        xhs_commands = commands_for_task("xiaohongshu", "阳朔 旅游", limit=3, freshness_window_hours=24, scroll_rounds=2)
        douyin_commands = commands_for_task("douyin", "阳朔 旅游", limit=3, freshness_window_hours=24, scroll_rounds=2)

        self.assertIn("https://www.xiaohongshu.com/search_result?keyword=", xhs_commands[0][-1])
        self.assertTrue(any("最新" in " ".join(command) and "一天内" in " ".join(command) for command in xhs_commands))
        self.assertIn("sort_type=2", douyin_commands[0][-1])
        self.assertIn("publish_time=1", douyin_commands[0][-1])
        self.assertTrue(any("search-result-card" in " ".join(command) for command in douyin_commands))
        self.assertTrue(any("waterfall_item_" in " ".join(command) for command in douyin_commands))

    def test_agent_collection_writes_real_rows_and_closes_sessions(self):
        calls = []
        agent_timeouts = []

        class Result:
            def __init__(self, stdout="", stderr="", returncode=0):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        def fake_runner(command, **_kwargs):
            calls.append(command)
            if command[:2] == ["opencli", "doctor"]:
                return Result(stdout="Everything looks good")
            if command[-1] == "close":
                return Result()
            if "eval" in command and "JSON.stringify(rows.slice" in command[-1]:
                return Result(
                    stdout=json.dumps(
                        [
                            {
                                "id": "xhs-1",
                                "platform": "xiaohongshu",
                                "query": "阳朔 旅游",
                                "title": "阳朔今日漓江玩法更新",
                                "body": "公开可见文本",
                                "url": "https://www.xiaohongshu.com/explore/1?xsec_token=secret&safe=1",
                                "author": "本地玩家",
                                "published_at_raw": "2小时前",
                                "ui_filter_applied": True,
                                "filter_labels": ["筛选", "最新", "一天内"],
                            }
                        ],
                        ensure_ascii=False,
                    )
                )
            return Result()

        def fake_agent_runner(command, **kwargs):
            agent_timeouts.append(kwargs.get("timeout", "missing"))
            return Result(
                stdout=json.dumps(
                    {
                        "decision": "APPROVED",
                        "reason": "按公开采集计划执行。",
                        "action_payload": {"actions": [{"action": "open", "target": "xiaohongshu:阳朔 旅游"}]},
                    },
                    ensure_ascii=False,
                )
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            agent_config = Path(temp_dir) / "agents.json"
            agent_config.write_text(
                json.dumps(
                    {
                        "default_agent": "hermes",
                        "agents": {
                            "hermes": {
                                "command": ["hermes", "-z", "{payload}"],
                                "timeout_seconds": None,
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = AgentCollectionConfig(
                platforms=["xiaohongshu"],
                queries=["阳朔 旅游"],
                target_per_platform=1,
                max_items_per_task=5,
                scroll_rounds_per_query=1,
                bundle_root=Path(temp_dir) / "bundles",
                artifact_root=Path(temp_dir) / "artifacts",
                log_root=Path(temp_dir) / "logs",
                agent_config=agent_config,
            )

            result = run_agent_collection(config, runner=fake_runner, agent_runner=fake_agent_runner, sleep_enabled=False)

            self.assertTrue(result["ok"])
            self.assertEqual(result["mode"], "agentCLI")
            self.assertEqual(result["counts"]["raw_items"], 1)
            self.assertEqual(result["counts"]["screened_items"], 1)
            bundle_path = Path(result["bundle"])
            raw_line = json.loads((bundle_path / "raw_items.jsonl").read_text(encoding="utf-8").splitlines()[0])
            decision_line = json.loads((bundle_path / "agent_decisions.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(raw_line["capture_method"], "agentcli_opencli_browser_bridge")
            self.assertNotIn("xsec_token", raw_line["url"])
            self.assertEqual(decision_line["decision"], "APPROVED")
            self.assertEqual(agent_timeouts, [None])
            self.assertTrue(any(command[-1] == "close" for command in calls))

    def test_agent_collection_stops_when_agent_returns_invalid_json_without_local_takeover(self):
        calls = []

        class Result:
            def __init__(self, stdout="", stderr="", returncode=0):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        def fake_runner(command, **_kwargs):
            calls.append(command)
            if command[:2] == ["opencli", "doctor"]:
                return Result(stdout="Everything looks good")
            raise AssertionError(f"OpenCLI collection should not run without an agent decision: {command}")

        def invalid_agent_runner(_command, **_kwargs):
            return Result(stdout="Hermes is still thinking or returned prose, not JSON")

        with tempfile.TemporaryDirectory() as temp_dir:
            agent_config = Path(temp_dir) / "agents.json"
            agent_config.write_text(
                json.dumps(
                    {
                        "default_agent": "hermes",
                        "agents": {
                            "hermes": {
                                "command": ["hermes", "-z", "{payload}"],
                                "timeout_seconds": None,
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = AgentCollectionConfig(
                platforms=["xiaohongshu"],
                queries=["阳朔 旅游"],
                bundle_root=Path(temp_dir) / "bundles",
                artifact_root=Path(temp_dir) / "artifacts",
                log_root=Path(temp_dir) / "logs",
                agent_config=agent_config,
            )

            result = run_agent_collection(config, runner=fake_runner, agent_runner=invalid_agent_runner, sleep_enabled=False)

            self.assertTrue(result["ok"])
            self.assertEqual(result["counts"]["raw_items"], 0)
            self.assertEqual(result["errors"][0]["status"], "agent_decision_invalid")
            bundle_path = Path(result["bundle"])
            decision_line = json.loads((bundle_path / "agent_decisions.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(decision_line["decision"], "NEED_HUMAN")
            self.assertNotIn("fallback", decision_line)
            self.assertEqual(calls, [["opencli", "doctor"]])

    def test_media_asr_downloads_extracts_and_writes_transcript_refs(self):
        calls = []

        class Result:
            def __init__(self, stdout="", stderr="", returncode=0):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        def fake_runner(command, **_kwargs):
            calls.append(command)
            if command[0] == "yt-dlp":
                template = Path(command[command.index("-o") + 1])
                (template.parent / "video.mp4").write_bytes(b"fake-video")
                return Result()
            if command[0] == "ffmpeg":
                Path(command[-1]).write_bytes(b"fake-audio")
                return Result()
            return Result(returncode=1, stderr="unexpected")

        def fake_transcriber(_audio_path, _backend, _config):
            return {
                "text": "阳朔遇龙河今天游客多，竹筏排队明显。",
                "segments": [{"start": 0, "end": 3.2, "text": "阳朔遇龙河今天游客多"}],
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            result = process_video_item(
                {"item_id": "dy-1", "platform": "douyin", "title": "阳朔视频", "url": "https://www.douyin.com/video/1"},
                Path(temp_dir),
                config=ASRConfig(backend="fake", browser_media_resolution=False),
                runner=fake_runner,
                transcriber=fake_transcriber,
            )

            self.assertEqual(result["download_status"], "done")
            self.assertEqual(result["asr_status"], "done")
            self.assertTrue(Path(result["transcript_ref"]).exists())
            self.assertTrue(Path(result["segments_ref"]).exists())
            self.assertIn("排队", result["summary"])
            self.assertEqual(calls[0][0], "yt-dlp")
            self.assertEqual(calls[1][0], "ffmpeg")

    def test_media_asr_prefers_browser_resolved_video_url_before_ytdlp(self):
        calls = []

        class Result:
            def __init__(self, stdout="", stderr="", returncode=0):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        def fake_runner(command, **_kwargs):
            calls.append(command)
            if command[:3] == ["opencli", "browser", "aetherflux-agentcli-media"]:
                if "eval" in command:
                    return Result(stdout=json.dumps({"video_urls": ["https://v26-web.douyinvod.com/video.mp4"], "image_urls": []}))
                return Result()
            if command[0] == "curl":
                Path(command[-1]).write_bytes(b"browser-video")
                return Result()
            if command[0] == "ffmpeg":
                Path(command[-1]).write_bytes(b"fake-audio")
                return Result()
            raise AssertionError(f"unexpected command: {command}")

        def fake_transcriber(_audio_path, _backend, _config):
            return {"text": "浏览器解析视频成功", "segments": [{"start": 0, "end": 1, "text": "浏览器解析视频成功"}]}

        with tempfile.TemporaryDirectory() as temp_dir:
            result = process_video_item(
                {"item_id": "dy-browser", "platform": "douyin", "content_type": "video", "title": "视频", "url": "https://www.douyin.com/video/1"},
                Path(temp_dir),
                config=ASRConfig(backend="fake", browser_media_resolution=True),
                runner=fake_runner,
                transcriber=fake_transcriber,
            )

            self.assertEqual(result["download_status"], "done")
            self.assertEqual(result["download_method"], "browser_media_url")
            self.assertFalse(any(command[0] == "yt-dlp" for command in calls))

    def test_media_asr_can_use_mlx_whisper_cli_when_python_module_is_not_importable(self):
        deps = {"ffmpeg": True, "yt_dlp": True, "mlx_whisper": False, "mlx_whisper_cli": True}

        self.assertEqual(select_asr_backend("auto", deps), "mlx_whisper_cli")
        self.assertEqual(select_asr_backend("mlx_whisper", deps), "mlx_whisper_cli")

    def test_dependency_status_does_not_crash_when_mlx_whisper_cli_is_missing(self):
        with patch("aetherflux_agentcli.media_asr.shutil.which", return_value=None), patch(
            "aetherflux_agentcli.media_asr._module_exists", return_value=False
        ):
            status = dependency_status()

        self.assertFalse(status["mlx_whisper_cli"])

    def test_information_value_marks_music_like_video_low_value(self):
        value = classify_information_value(
            {"title": "阳朔遇龙河竹筏视频", "body": "#阳朔遇龙河竹筏#旅游景区打卡 #夏天游山玩水胜地推荐"},
            "為戰精山不見軍但精方言如生命為戰精山不見軍但精方言如生命",
            [],
            content_type="video",
        )

        self.assertEqual(value["status"], "low_value")
        self.assertIn("asr_low_signal", value["reasons"])

    def test_information_value_keeps_actionable_transcript(self):
        value = classify_information_value(
            {"title": "阳朔避坑", "body": "遇龙河竹筏"},
            "今天遇龙河竹筏排队两个小时，建议早上八点前到。",
            [],
            content_type="video",
        )

        self.assertEqual(value["status"], "useful")
        self.assertIn("risk_or_opportunity_terms", value["reasons"])

    def test_media_asr_downloads_douyin_image_posts_without_asr(self):
        calls = []

        class Result:
            def __init__(self, stdout="", stderr="", returncode=0):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        def fake_runner(command, **_kwargs):
            calls.append(command)
            if command[:3] == ["opencli", "browser", "aetherflux-agentcli-media"]:
                if "eval" in command:
                    return Result(stdout=json.dumps({"video_urls": [], "image_urls": ["https://p3.douyinpic.com/a.jpeg", "https://p3.douyinpic.com/b.jpeg"]}))
                return Result()
            if command[0] == "curl":
                Path(command[-1]).write_bytes(b"image")
                return Result()
            raise AssertionError(f"unexpected command: {command}")

        with tempfile.TemporaryDirectory() as temp_dir:
            result = process_video_item(
                {
                    "item_id": "dy-image-1",
                    "platform": "douyin",
                    "content_type": "image",
                    "title": "阳朔图文",
                    "url": "https://www.douyin.com/note/1",
                },
                Path(temp_dir),
                config=ASRConfig(browser_media_resolution=True),
                runner=fake_runner,
            )

            self.assertEqual(result["download_status"], "skipped")
            self.assertEqual(result["asr_status"], "skipped")
            self.assertEqual(result["error"], "not_video_content")
            self.assertEqual(len(result["image_refs"]), 2)

    def test_agent_collection_runs_video_asr_for_screened_items_with_urls(self):
        calls = []

        class Result:
            def __init__(self, stdout="", stderr="", returncode=0):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        def fake_runner(command, **_kwargs):
            calls.append(command)
            if command[:2] == ["opencli", "doctor"]:
                return Result(stdout="Everything looks good")
            if command[-1] == "close":
                return Result()
            if command[0] == "yt-dlp":
                template = Path(command[command.index("-o") + 1])
                (template.parent / "video.mp4").write_bytes(b"fake-video")
                return Result()
            if command[0] == "ffmpeg":
                Path(command[-1]).write_bytes(b"fake-audio")
                return Result()
            if "eval" in command and "JSON.stringify(rows.slice" in command[-1]:
                return Result(
                    stdout=json.dumps(
                        [
                            {
                                "id": "dy-1",
                                "platform": "douyin",
                                "query": "阳朔 旅游",
                                "title": "阳朔今日视频",
                                "body": "00:12 旅游攻略 @作者 · 2小时前",
                                "url": "https://www.douyin.com/video/1",
                                "author": "作者",
                                "published_at_raw": "2小时前",
                                "ui_filter_applied": True,
                            }
                        ],
                        ensure_ascii=False,
                    )
                )
            return Result()

        def fake_agent_runner(_command, **_kwargs):
            return Result(
                stdout=json.dumps(
                    {
                        "decision": "APPROVED",
                        "reason": "允许公开采集。",
                        "action_payload": {"actions": [{"action": "open", "target": "douyin:阳朔 旅游"}]},
                    },
                    ensure_ascii=False,
                )
            )

        def fake_transcriber(_audio_path, _backend, _config):
            return {"text": "阳朔旅游攻略视频转写", "segments": [{"start": 0, "end": 2, "text": "阳朔旅游攻略"}]}

        with tempfile.TemporaryDirectory() as temp_dir:
            agent_config = Path(temp_dir) / "agents.json"
            agent_config.write_text(
                json.dumps(
                    {"default_agent": "hermes", "agents": {"hermes": {"command": ["hermes", "-z", "{payload}"], "timeout_seconds": None}}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = AgentCollectionConfig(
                platforms=["douyin"],
                queries=["阳朔 旅游"],
                bundle_root=Path(temp_dir) / "bundles",
                artifact_root=Path(temp_dir) / "artifacts",
                log_root=Path(temp_dir) / "logs",
                media_root=Path(temp_dir) / "media",
                agent_config=agent_config,
                asr_backend="fake",
            )

            result = run_agent_collection(
                config,
                runner=fake_runner,
                agent_runner=fake_agent_runner,
                sleep_enabled=False,
                transcriber=fake_transcriber,
            )

            self.assertEqual(result["counts"]["asr_results"], 1)
            bundle_path = Path(result["bundle"])
            asr_line = json.loads((bundle_path / "asr_results.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(asr_line["asr_status"], "done")
            self.assertEqual(asr_line["download_status"], "done")
            self.assertTrue(Path(asr_line["transcript_ref"]).exists())


if __name__ == "__main__":
    unittest.main()
