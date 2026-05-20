#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DB_PATH="${AETHERFLUX_DB:-data/aetherflux.db}"
WEBHOOK_URL="${AETHERFLUX_WEBHOOK_URL:-}"

python3 -m aetherflux.cli --db "$DB_PATH" ingest
python3 -m aetherflux.cli --db "$DB_PATH" review --webhook-url "$WEBHOOK_URL"
