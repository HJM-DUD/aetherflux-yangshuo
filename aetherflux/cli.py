"""Command line entry points for the Yangshuo intelligence system."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .deepseek import DeepSeekAdvisorError
from .pipeline import run_ingest, run_review
from .server import run_server
from .storage import IntelligenceStore
from .xhs import JSONFeedXHSDriver, collect_xhs, parse_now


DEFAULT_DB = Path("data/aetherflux.db")
DEFAULT_DIRECTIONS = Path("config/directions.json")
DEFAULT_SEED = Path("data/seed_items.json")
DEFAULT_XHS_SOURCE = Path("data/xhs_source_items.json")
DEFAULT_XHS_OUTPUT = Path("artifacts/xhs_raw_items.json")
DEFAULT_XHS_STATE = Path("artifacts/xhs_collect_state.json")
DEFAULT_DASHBOARD_PORT = 8788
DEFAULT_WORKER_API_PORT = 8789


def main() -> None:
    parser = argparse.ArgumentParser(description="AetherFlux Yangshuo intelligence system")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    subcommands = parser.add_subparsers(dest="command", required=True)

    ingest = subcommands.add_parser("ingest", help="Run low-token scripted ingest")
    ingest.add_argument("--directions", default=str(DEFAULT_DIRECTIONS))
    ingest.add_argument("--seed", default=str(DEFAULT_SEED))

    review = subcommands.add_parser("review", help="Generate Mac Codex review draft")
    review.add_argument("--webhook-url", default="")
    review.add_argument("--top-n", type=int, default=20)

    serve = subcommands.add_parser("serve", help="Run local dashboard and API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=DEFAULT_DASHBOARD_PORT)

    xhs = subcommands.add_parser("xhs", help="Run Xiaohongshu collection")
    xhs_subcommands = xhs.add_subparsers(dest="xhs_command", required=True)

    xhs_backfill = xhs_subcommands.add_parser("backfill", help="Collect recent Xiaohongshu notes")
    xhs_backfill.add_argument("--days", type=int, default=7)
    _add_xhs_common_args(xhs_backfill)

    xhs_daily = xhs_subcommands.add_parser("daily", help="Collect Xiaohongshu notes newer than the saved watermark")
    _add_xhs_common_args(xhs_daily)

    args = parser.parse_args()

    if args.command == "ingest":
        store = IntelligenceStore(args.db)
        store.initialize()
        result = run_ingest(store, args.directions, args.seed)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "review":
        store = IntelligenceStore(args.db)
        store.initialize()
        try:
            draft = run_review(store, args.webhook_url, top_n=args.top_n)
        except DeepSeekAdvisorError as exc:
            print(json.dumps({"ok": False, "error": "deepseek_failed", "message": str(exc)}, ensure_ascii=False, indent=2))
            sys.exit(2)
        print(json.dumps(draft, ensure_ascii=False, indent=2))
    elif args.command == "serve":
        store = IntelligenceStore(args.db)
        store.initialize()
        run_server(store, args.host, args.port)
    elif args.command == "xhs":
        result = _run_xhs_command(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))


def _add_xhs_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", default=str(DEFAULT_XHS_SOURCE), help="JSON feed captured by a logged-in browser driver")
    parser.add_argument("--output", default=str(DEFAULT_XHS_OUTPUT), help="Raw item JSON output for later ingest")
    parser.add_argument("--state", default=str(DEFAULT_XHS_STATE), help="Persistent XHS collection state")
    parser.add_argument("--now", default="", help="Override current UTC time for deterministic runs")


def _run_xhs_command(args: argparse.Namespace) -> dict:
    now = parse_now(args.now) if args.now else None
    return collect_xhs(
        driver=JSONFeedXHSDriver(args.source),
        mode=args.xhs_command,
        state_path=args.state,
        output_path=args.output,
        days=getattr(args, "days", 7),
        now=now,
    )


if __name__ == "__main__":
    main()
