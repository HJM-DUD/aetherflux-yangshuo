#!/usr/bin/env bash
set -euo pipefail

PORT="${AETHERFLUX_CHROME_CDP_PORT:-9222}"
PROFILE_DIR="${AETHERFLUX_CHROME_PROFILE:-$HOME/Library/Application Support/AetherFlux/ChromeProfile}"

mkdir -p "$PROFILE_DIR"

echo "Opening AetherFlux Chrome profile with remote debugging on port ${PORT}."
echo "Profile: ${PROFILE_DIR}"
echo "Log in to Xiaohongshu and Douyin in this Chrome window before running live collection."

open -na "Google Chrome" --args \
  --remote-debugging-port="$PORT" \
  --user-data-dir="$PROFILE_DIR" \
  --no-first-run \
  --no-default-browser-check
