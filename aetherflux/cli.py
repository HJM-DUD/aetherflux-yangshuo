"""Command line entry points for the Yangshuo intelligence system."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .deepseek import DeepSeekAdvisorError
from .live_collectors import BrowserConnectionError, collect_live_platform
from .live_rotation import DEFAULT_CONFIG as DEFAULT_LIVE_CONFIG
from .live_rotation import run_rotation_collection
from .opencli_collectors import run_opencli_rotation
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
DEFAULT_LIVE_OUTPUT = Path("artifacts/live_raw_items.json")
DEFAULT_DASHBOARD_PORT = 8788
DEFAULT_WORKER_API_PORT = 8789


def main() -> None:
    parser = argparse.ArgumentParser(description="AetherFlux local-first intelligence system")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    subcommands = parser.add_subparsers(dest="command", required=True)

    ingest = subcommands.add_parser(
        "ingest",
        help="Ingest a local JSON feed or seed file; not live platform crawling",
        description="Ingest a local JSON feed or seed file into SQLite. This is not live platform crawling.",
    )
    ingest.add_argument("--directions", default=str(DEFAULT_DIRECTIONS), help="Local directions JSON")
    ingest.add_argument("--seed", default=str(DEFAULT_SEED), help="Local JSON feed or seed file")

    review = subcommands.add_parser("review", help="Generate a review draft from local SQLite candidates")
    review.add_argument("--webhook-url", default="")
    review.add_argument("--top-n", type=int, default=20)

    serve = subcommands.add_parser(
        "serve",
        help="Run V0.2.4 FastAPI admin backend",
        description="Run V0.2.4 FastAPI admin backend on 127.0.0.1 by default.",
    )
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=DEFAULT_DASHBOARD_PORT)

    legacy_serve = subcommands.add_parser("legacy-serve", help="Run the deprecated V0.1 static dashboard shell")
    legacy_serve.add_argument("--host", default="127.0.0.1")
    legacy_serve.add_argument("--port", type=int, default=DEFAULT_DASHBOARD_PORT)

    xhs = subcommands.add_parser("xhs", help="Process Xiaohongshu JSON feed snapshots")
    xhs_subcommands = xhs.add_subparsers(dest="xhs_command", required=True)

    xhs_backfill = xhs_subcommands.add_parser(
        "backfill",
        help="Process recent Xiaohongshu JSON feed snapshots; not a live Xiaohongshu crawler",
        description="Process recent Xiaohongshu JSON feed snapshots. This command is not a live Xiaohongshu crawler.",
    )
    xhs_backfill.add_argument("--days", type=int, default=7)
    _add_xhs_common_args(xhs_backfill)

    xhs_daily = xhs_subcommands.add_parser(
        "daily",
        help="Process Xiaohongshu JSON feed items newer than the saved watermark; not a live Xiaohongshu crawler",
        description="Process Xiaohongshu JSON feed items newer than the saved watermark. This command is not a live Xiaohongshu crawler.",
    )
    _add_xhs_common_args(xhs_daily)

    live = subcommands.add_parser(
        "live",
        help="Collect visible public items from logged-in Chrome via CDP for xiaohongshu or douyin",
        description=(
            "Collect visible public items from logged-in Chrome via Chrome DevTools Protocol. "
            "Supported platforms: xiaohongshu, douyin. WeChat Channels is intentionally skipped."
        ),
    )
    live.add_argument("platform", choices=["xiaohongshu", "douyin"])
    live.add_argument("--query", required=True)
    live.add_argument("--cluster-id", default="manual")
    live.add_argument("--max-items", type=int, default=30)
    live.add_argument("--detail-limit", type=int, default=5, help="Open detail pages for the first N search results")
    live.add_argument("--cdp-url", default="http://127.0.0.1:9222")
    live.add_argument("--output", default=str(DEFAULT_LIVE_OUTPUT))

    live_rotate = subcommands.add_parser(
        "live-rotate",
        help="Run adaptive slow rotating collection across logged-in live platforms",
        description=(
            "Run adaptive slow collection across platforms one item at a time. "
            "Default config is config/live_collect.json. Use --dry-run to print the rotation plan."
        ),
    )
    live_rotate.add_argument("--config", default=str(DEFAULT_LIVE_CONFIG))
    live_rotate.add_argument("--cdp-url", default="http://127.0.0.1:9222")
    live_rotate.add_argument("--output-dir", default="artifacts/live")
    live_rotate.add_argument("--log-dir", default="logs/live")
    live_rotate.add_argument("--dry-run", action="store_true")
    live_rotate.add_argument("--no-sleep", action="store_true", help="Disable real waits; intended for tests and diagnostics")

    opencli_rotate = subcommands.add_parser(
        "opencli-rotate",
        help="Run OpenCLI Browser Bridge rotating collection across logged-in platforms",
        description=(
            "Run OpenCLI Browser Bridge collection across platforms one item at a time. "
            "Default config is config/live_collect.json. Use --dry-run to print the rotation plan."
        ),
    )
    opencli_rotate.add_argument("--config", default=str(DEFAULT_LIVE_CONFIG))
    opencli_rotate.add_argument("--output-dir", default="artifacts/opencli/live")
    opencli_rotate.add_argument("--log-dir", default="logs/opencli/live")
    opencli_rotate.add_argument("--stage", choices=["titles", "screen", "videos", "all"], default="all")
    opencli_rotate.add_argument("--dry-run", action="store_true")
    opencli_rotate.add_argument("--no-sleep", action="store_true", help="Disable real waits; intended for tests and diagnostics")

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
        import uvicorn
        from .admin_api import create_app

        uvicorn.run(create_app(store), host=args.host, port=args.port)
    elif args.command == "legacy-serve":
        store = IntelligenceStore(args.db)
        store.initialize()
        run_server(store, args.host, args.port)
    elif args.command == "xhs":
        result = _run_xhs_command(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "live":
        try:
            items = collect_live_platform(
                args.platform,
                args.query,
                cdp_url=args.cdp_url,
                max_items=args.max_items,
                cluster_id=args.cluster_id,
                detail_limit=args.detail_limit,
            )
        except BrowserConnectionError as exc:
            print(json.dumps({"ok": False, "error": "browser_connection_failed", "message": str(exc)}, ensure_ascii=False, indent=2))
            sys.exit(2)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"ok": True, "platform": args.platform, "stored": len(items), "output": str(output_path)}, ensure_ascii=False, indent=2))
    elif args.command == "live-rotate":
        result = run_rotation_collection(
            config_path=args.config,
            cdp_url=args.cdp_url,
            output_dir=args.output_dir,
            log_dir=args.log_dir,
            dry_run=args.dry_run,
            sleep_enabled=not args.no_sleep,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "opencli-rotate":
        result = run_opencli_rotation(
            config_path=args.config,
            output_dir=args.output_dir,
            log_dir=args.log_dir,
            dry_run=args.dry_run,
            sleep_enabled=not args.no_sleep,
            stage=args.stage,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result.get("ok", False):
            sys.exit(2)


def _add_xhs_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", default=str(DEFAULT_XHS_SOURCE), help="JSON feed captured by a separate browser driver or manual export")
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
