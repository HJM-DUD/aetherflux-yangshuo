#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

AETHERFLUX_CDP_URL="${AETHERFLUX_CDP_URL:-http://127.0.0.1:9222}"
AETHERFLUX_LIVE_CONFIG="${AETHERFLUX_LIVE_CONFIG:-config/live_collect.json}"
AETHERFLUX_OUTPUT_DIR="${AETHERFLUX_OUTPUT_DIR:-artifacts/live}"
AETHERFLUX_LOG_DIR="${AETHERFLUX_LOG_DIR:-logs/live}"
AETHERFLUX_DRY_RUN="${AETHERFLUX_DRY_RUN:-0}"
AETHERFLUX_COLLECT_BACKEND="${AETHERFLUX_COLLECT_BACKEND:-opencli}"

mkdir -p "$AETHERFLUX_OUTPUT_DIR"
mkdir -p "$AETHERFLUX_LOG_DIR"

check_cdp() {
  if [[ "$AETHERFLUX_DRY_RUN" == "1" ]]; then
    return 0
  fi

  if ! curl -fsS "${AETHERFLUX_CDP_URL%/}/json/version" >/dev/null 2>&1; then
    cat >&2 <<EOF
Chrome CDP is not reachable: ${AETHERFLUX_CDP_URL}

请先运行：
  scripts/open_chrome_cdp.sh

然后在打开的专用 Chrome 窗口里手动登录小红书和抖音，再重新运行本脚本。
EOF
    exit 2
  fi
}

main() {
  if [[ "$AETHERFLUX_COLLECT_BACKEND" == "opencli" ]]; then
    scripts/hermes_collect_opencli.sh
    return 0
  fi

  if [[ "$AETHERFLUX_COLLECT_BACKEND" != "cdp" ]]; then
    echo "Unsupported AETHERFLUX_COLLECT_BACKEND=${AETHERFLUX_COLLECT_BACKEND}. Use opencli or cdp." >&2
    exit 2
  fi

  check_cdp

  if [[ "$AETHERFLUX_DRY_RUN" == "1" ]]; then
    python3 -m aetherflux.cli live-rotate \
      --config "$AETHERFLUX_LIVE_CONFIG" \
      --cdp-url "$AETHERFLUX_CDP_URL" \
      --output-dir "$AETHERFLUX_OUTPUT_DIR" \
      --log-dir "$AETHERFLUX_LOG_DIR" \
      --dry-run \
      --no-sleep
    return 0
  fi

  python3 -m aetherflux.cli live-rotate \
    --config "$AETHERFLUX_LIVE_CONFIG" \
    --cdp-url "$AETHERFLUX_CDP_URL" \
    --output-dir "$AETHERFLUX_OUTPUT_DIR" \
    --log-dir "$AETHERFLUX_LOG_DIR"
}

main "$@"
