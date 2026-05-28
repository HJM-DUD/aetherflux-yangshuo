#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

AETHERFLUX_LIVE_CONFIG="${AETHERFLUX_LIVE_CONFIG:-config/live_collect.json}"
AETHERFLUX_OUTPUT_DIR="${AETHERFLUX_OUTPUT_DIR:-artifacts/opencli/live}"
AETHERFLUX_LOG_DIR="${AETHERFLUX_LOG_DIR:-logs/opencli/live}"
AETHERFLUX_DRY_RUN="${AETHERFLUX_DRY_RUN:-0}"
AETHERFLUX_OPENCLI_STAGE="${AETHERFLUX_OPENCLI_STAGE:-all}"
export AETHERFLUX_HERMES_SCREEN="${AETHERFLUX_HERMES_SCREEN:-1}"

mkdir -p "$AETHERFLUX_OUTPUT_DIR"
mkdir -p "$AETHERFLUX_LOG_DIR"

check_opencli() {
  if [[ "$AETHERFLUX_DRY_RUN" == "1" ]]; then
    return 0
  fi

  if ! opencli doctor; then
    cat >&2 <<EOF
OpenCLI Browser Bridge is not ready.

请先确认：
  1. Chrome 已启用 OpenCLI Browser Bridge 扩展
  2. opencli daemon restart 已执行
  3. opencli doctor 返回 Everything looks good

OpenCLI 未打通时，本脚本不会继续采集，避免再次产生假成功数据。
EOF
    exit 2
  fi
}

main() {
  check_opencli

  if [[ "$AETHERFLUX_DRY_RUN" == "1" ]]; then
    python3 -m aetherflux.cli opencli-rotate \
      --config "$AETHERFLUX_LIVE_CONFIG" \
      --output-dir "$AETHERFLUX_OUTPUT_DIR" \
      --log-dir "$AETHERFLUX_LOG_DIR" \
      --stage "$AETHERFLUX_OPENCLI_STAGE" \
      --dry-run \
      --no-sleep
    return 0
  fi

  python3 -m aetherflux.cli opencli-rotate \
    --config "$AETHERFLUX_LIVE_CONFIG" \
    --output-dir "$AETHERFLUX_OUTPUT_DIR" \
    --log-dir "$AETHERFLUX_LOG_DIR" \
    --stage "$AETHERFLUX_OPENCLI_STAGE"
}

main "$@"
