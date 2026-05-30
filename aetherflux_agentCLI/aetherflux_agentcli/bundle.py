"""Daily bundle writer shared by the agentCLI workflow."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


BUNDLE_VERSION = "0.2.7"
JSONL_FILES = {
    "raw_items": "raw_items.jsonl",
    "screened_items": "screened_items.jsonl",
    "asr_results": "asr_results.jsonl",
    "agent_decisions": "agent_decisions.jsonl",
    "errors": "errors.jsonl",
}


@dataclass(frozen=True)
class BundleResult:
    path: Path
    manifest: Dict[str, Any]


class BundleWriter:
    def __init__(self, root: str | Path, mode: str, node_id: str) -> None:
        self.root = Path(root)
        self.mode = mode
        self.node_id = node_id

    def create_bundle(
        self,
        bundle_date: str,
        run_id: str,
        mission: Mapping[str, Any],
        raw_items: Iterable[Mapping[str, Any]],
        screened_items: Iterable[Mapping[str, Any]],
        asr_results: Iterable[Mapping[str, Any]],
        agent_decisions: Iterable[Mapping[str, Any]],
        errors: Iterable[Mapping[str, Any]],
    ) -> BundleResult:
        bundle_path = self.root / f"daily_bundle_{bundle_date}" / run_id
        bundle_path.mkdir(parents=True, exist_ok=True)
        rows = {
            "raw_items": [dict(item) for item in raw_items],
            "screened_items": [dict(item) for item in screened_items],
            "asr_results": [dict(item) for item in asr_results],
            "agent_decisions": [dict(item) for item in agent_decisions],
            "errors": [dict(item) for item in errors],
        }
        for key, filename in JSONL_FILES.items():
            _write_jsonl(bundle_path / filename, rows[key])
        files = [_file_info(bundle_path, filename) for filename in JSONL_FILES.values()]
        manifest = {
            "version": BUNDLE_VERSION,
            "mode": self.mode,
            "bundle_date": bundle_date,
            "run_id": run_id,
            "node_id": self.node_id,
            "mission": dict(mission),
            "counts": {key: len(value) for key, value in rows.items()},
            "files": files,
            "contains_raw_media": False,
            "handoff": "local_bundle_for_super_brain",
        }
        (bundle_path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["files"].append(_file_info(bundle_path, "manifest.json"))
        (bundle_path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return BundleResult(path=bundle_path, manifest=manifest)


def copy_bundle_to_inbox(bundle_path: str | Path, inbox_root: str | Path) -> Path:
    source = Path(bundle_path)
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    target = Path(inbox_root) / manifest["mode"] / manifest["bundle_date"] / manifest["run_id"]
    if target.exists():
        raise FileExistsError(f"Bundle inbox target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return target


def _write_jsonl(path: Path, rows: List[Mapping[str, Any]]) -> None:
    text = "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def _file_info(root: Path, relative_path: str) -> Dict[str, Any]:
    path = root / relative_path
    data = path.read_bytes()
    return {
        "relative_path": relative_path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
    }
