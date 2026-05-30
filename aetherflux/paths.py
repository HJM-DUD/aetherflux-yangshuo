"""Central data-path resolution for AetherFlux.

All runtime data (DB, artifacts, logs, bundles) lives under
AETHERFLUX_DATA_ROOT, defaulting to /Users/gugu/Documents/Agent/AetherFlux_Data.
"""

import os
from pathlib import Path

_DATA_ROOT = Path(os.environ.get("AETHERFLUX_DATA_ROOT", "/Users/gugu/Documents/Agent/AetherFlux_Data"))


def data_root() -> Path:
    """Return the configured data root directory."""
    return _DATA_ROOT


def ensure_dir(p: Path) -> Path:
    """Create directory if missing and return it."""
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── Main-project paths ──────────────────────────────────────────────

def db_path() -> Path:
    return ensure_dir(_DATA_ROOT) / "aetherflux.db"


def seed_items_path() -> Path:
    return _DATA_ROOT / "seed_items.json"


def xhs_source_path() -> Path:
    return _DATA_ROOT / "xhs_source_items.json"


def xhs_output_path() -> Path:
    return ensure_dir(_DATA_ROOT / "artifacts") / "xhs_raw_items.json"


def xhs_state_path() -> Path:
    return ensure_dir(_DATA_ROOT / "artifacts") / "xhs_collect_state.json"


def live_output_path() -> Path:
    return ensure_dir(_DATA_ROOT / "artifacts") / "live_raw_items.json"


def deepseek_status_path() -> Path:
    return ensure_dir(_DATA_ROOT / "artifacts") / "deepseek_status.json"


# ── Artifacts / logs / media ────────────────────────────────────────

def artifacts_dir() -> Path:
    return ensure_dir(_DATA_ROOT / "artifacts")


def logs_dir() -> Path:
    return ensure_dir(_DATA_ROOT / "logs")


def opencli_live_output_dir() -> Path:
    return ensure_dir(_DATA_ROOT / "artifacts" / "opencli" / "live")


def opencli_live_log_dir() -> Path:
    return ensure_dir(_DATA_ROOT / "logs" / "opencli" / "live")


def opencli_media_dir(run_id: str = "") -> Path:
    d = _DATA_ROOT / "artifacts" / "media"
    if run_id:
        d = d / run_id[:8]
    return ensure_dir(d)


def live_rotate_output_dir() -> Path:
    return ensure_dir(_DATA_ROOT / "artifacts" / "live")


def live_rotate_log_dir() -> Path:
    return ensure_dir(_DATA_ROOT / "logs" / "live")


# ── Daily bundles inbox ─────────────────────────────────────────────

def daily_bundles_inbox_dir() -> Path:
    return ensure_dir(_DATA_ROOT / "daily_bundles_inbox")


# ── Sub-project paths ───────────────────────────────────────────────

def agentcli_bundle_root() -> Path:
    return ensure_dir(_DATA_ROOT / "agentCLI" / "daily_bundles")


def agentcli_artifact_root() -> Path:
    return ensure_dir(_DATA_ROOT / "artifacts" / "opencli" / "agent")


def agentcli_log_root() -> Path:
    return ensure_dir(_DATA_ROOT / "logs" / "opencli" / "agent")


def agentcli_media_root() -> Path:
    return ensure_dir(_DATA_ROOT / "artifacts" / "media" / "agent")


def shellcli_bundle_root() -> Path:
    return ensure_dir(_DATA_ROOT / "shellCLI" / "daily_bundles")


def shellcli_artifact_root() -> Path:
    return ensure_dir(_DATA_ROOT / "artifacts" / "opencli" / "live")


def shellcli_log_root() -> Path:
    return ensure_dir(_DATA_ROOT / "logs" / "opencli" / "live")
