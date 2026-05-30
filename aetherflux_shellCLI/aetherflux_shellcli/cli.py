"""CLI hooks for shellCLI collector workflow."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict

from .collector import ShellCollectionConfig, load_config, plan_supported_tasks, run_shell_collection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AetherFlux V0.2.5 shellCLI collector")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "scheduler-hook", "backend-hook"):
        command = subcommands.add_parser(name)
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--config", default="config/collect.json")
        command.add_argument("--stage", choices=["titles", "screen", "videos", "all"], default="all")
        command.add_argument("--no-sleep", action="store_true")
        command.add_argument("--bundle-root", default="data/daily_bundles")
        command.add_argument("--main-inbox", default="")
    return parser


def run(args: argparse.Namespace) -> Dict[str, Any]:
    config = load_config(args.config)
    config.bundle_root = args.bundle_root
    if args.main_inbox:
        config.main_inbox = args.main_inbox
    tasks, errors = plan_supported_tasks(config.normalized_platforms(), config.normalized_queries(), per_platform=config.target_per_platform)
    if args.dry_run:
        return {"ok": True, "mode": "shellCLI", "dry_run": True, "tasks": tasks, "errors": errors}
    return run_shell_collection(config, sleep_enabled=not args.no_sleep, stage=args.stage)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
