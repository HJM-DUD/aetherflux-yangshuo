#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DB_PATH="${AETHERFLUX_DB:-/Users/gugu/Documents/Agent/AetherFlux_Data/aetherflux.db}"
WEBHOOK_URL="${AETHERFLUX_WEBHOOK_URL:-}"

echo "AetherFlux V0.2 note: daily_review.sh runs local JSON/seed ingest + review only."
echo "It does not perform live Xiaohongshu/Douyin/WeChat Channels crawling."

python3 -m aetherflux.cli --db "$DB_PATH" ingest
python3 -m aetherflux.cli --db "$DB_PATH" review --webhook-url "$WEBHOOK_URL"
