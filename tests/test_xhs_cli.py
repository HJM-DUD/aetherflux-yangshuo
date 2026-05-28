import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class XHSCLITests(unittest.TestCase):
    def test_xhs_backfill_and_daily_write_raw_items_for_ingest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.json"
            backfill_output = root / "backfill.json"
            daily_output = root / "daily.json"
            state_path = root / "state.json"
            source_path.write_text(
                json.dumps(
                    [
                        {
                            "title": "遇龙河竹筏排队",
                            "body": "今天很多人关注票务指引",
                            "url": "https://xhs.example/note/1",
                            "published_at": "2026-05-20T08:00:00Z",
                            "query": "阳朔 遇龙河 竹筏",
                        },
                        {
                            "title": "阳朔旧笔记",
                            "body": "超过首采窗口",
                            "url": "https://xhs.example/note/old",
                            "published_at": "2026-05-01T08:00:00Z",
                            "query": "阳朔 遇龙河 竹筏",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            backfill = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "aetherflux.cli",
                    "xhs",
                    "backfill",
                    "--days",
                    "7",
                    "--source",
                    str(source_path),
                    "--output",
                    str(backfill_output),
                    "--state",
                    str(state_path),
                    "--now",
                    "2026-05-20T12:00:00Z",
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=True,
                capture_output=True,
                text=True,
            )
            backfill_result = json.loads(backfill.stdout)

            daily = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "aetherflux.cli",
                    "xhs",
                    "daily",
                    "--source",
                    str(source_path),
                    "--output",
                    str(daily_output),
                    "--state",
                    str(state_path),
                    "--now",
                    "2026-05-20T13:00:00Z",
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=True,
                capture_output=True,
                text=True,
            )
            daily_result = json.loads(daily.stdout)

            self.assertEqual(backfill_result["stored"], 1)
            self.assertEqual(daily_result["stored"], 0)
            self.assertEqual(json.loads(backfill_output.read_text(encoding="utf-8"))[0]["platform"], "xiaohongshu")
            self.assertEqual(json.loads(daily_output.read_text(encoding="utf-8")), [])


if __name__ == "__main__":
    unittest.main()
