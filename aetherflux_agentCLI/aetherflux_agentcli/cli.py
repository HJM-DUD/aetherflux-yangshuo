"""CLI hooks for agentCLI autonomous crawler workflow."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict

from .bundle import BundleWriter, copy_bundle_to_inbox


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AetherFlux V0.2.5 agentCLI crawler")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "scheduler-hook", "backend-hook"):
        command = subcommands.add_parser(name)
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--bundle-root", default="data/daily_bundles")
        command.add_argument("--main-inbox", default="")
    return parser


def run(args: argparse.Namespace) -> Dict[str, Any]:
    bundle_date = datetime.now(timezone.utc).date().isoformat()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.dry_run:
        return {
            "ok": True,
            "mode": "agentCLI",
            "dry_run": True,
            "allowed_actions": ["open", "click", "fill", "scroll", "wait", "extract"],
            "hard_stop": ["login", "captcha", "account_settings", "publish", "payment", "delete", "upload"],
        }
    bundle = BundleWriter(args.bundle_root, mode="agentCLI", node_id="local").create_bundle(
        bundle_date=bundle_date,
        run_id=run_id,
        mission={"place": "阳朔", "industry": "旅游"},
        raw_items=[],
        screened_items=[],
        asr_results=[],
        agent_decisions=[],
        errors=[],
    )
    copied = copy_bundle_to_inbox(bundle.path, args.main_inbox) if args.main_inbox else None
    return {"ok": True, "mode": "agentCLI", "bundle": str(bundle.path), "copied_to": str(copied) if copied else ""}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
