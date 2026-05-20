"""Command line entry points for the Yangshuo intelligence system."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_ingest, run_review
from .server import run_server
from .storage import IntelligenceStore


DEFAULT_DB = Path("data/aetherflux.db")
DEFAULT_DIRECTIONS = Path("config/directions.json")
DEFAULT_SEED = Path("data/seed_items.json")


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
    serve.add_argument("--port", type=int, default=8765)

    args = parser.parse_args()
    store = IntelligenceStore(args.db)
    store.initialize()

    if args.command == "ingest":
        result = run_ingest(store, args.directions, args.seed)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "review":
        draft = run_review(store, args.webhook_url, top_n=args.top_n)
        print(json.dumps(draft, ensure_ascii=False, indent=2))
    elif args.command == "serve":
        run_server(store, args.host, args.port)


if __name__ == "__main__":
    main()
