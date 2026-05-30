"""CLI hooks for agentCLI autonomous crawler workflow."""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict

from .collector import AgentCollectionConfig, load_config, plan_supported_tasks, run_agent_collection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AetherFlux V0.2.5 agentCLI crawler")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "scheduler-hook", "backend-hook"):
        command = subcommands.add_parser(name)
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--config", default="config/collect.json")
        command.add_argument("--stage", choices=["titles", "screen", "videos", "all"], default="all")
        command.add_argument("--no-sleep", action="store_true")
        command.add_argument("--bundle-root", default=str(_DATA_ROOT / "agentCLI" / "daily_bundles"))
        command.add_argument("--main-inbox", default="")
        command.add_argument("--platforms", nargs="*", default=None)
        command.add_argument("--queries", nargs="*", default=None)
    return parser


def run(args: argparse.Namespace) -> Dict[str, Any]:
    config: AgentCollectionConfig = load_config(args.config)
    config.bundle_root = args.bundle_root
    if args.main_inbox:
        config.main_inbox = args.main_inbox
    platforms = list(args.platforms) if args.platforms else None
    queries = list(args.queries) if args.queries else None
    effective_platforms = platforms or config.normalized_platforms()
    effective_queries = queries or config.normalized_queries()
    tasks, errors = plan_supported_tasks(effective_platforms, effective_queries, per_platform=config.target_per_platform)
    if args.dry_run:
        return {
            "ok": True,
            "mode": "agentCLI",
            "dry_run": True,
            "tasks": tasks,
            "errors": errors,
            "allowed_actions": ["open", "click", "fill", "scroll", "wait", "extract"],
            "hard_stop": ["login", "captcha", "account_settings", "publish", "payment", "delete", "upload"],
        }
    return run_agent_collection(
        config,
        sleep_enabled=not args.no_sleep,
        stage=args.stage,
        platforms_override=platforms,
        queries_override=queries,
    )



import os as _os
from pathlib import Path as _Path
_DATA_ROOT = _Path(_os.environ.get("AETHERFLUX_DATA_ROOT", "/Users/gugu/Documents/Agent/AetherFlux_Data"))

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
