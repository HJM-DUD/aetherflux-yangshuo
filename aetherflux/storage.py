"""SQLite storage for candidates, review drafts, and human decisions."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional


class IntelligenceStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    body TEXT,
                    source TEXT,
                    platform TEXT,
                    url TEXT,
                    published_at TEXT,
                    language TEXT,
                    category TEXT,
                    score INTEGER NOT NULL,
                    dedupe_key TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS decisions (
                    candidate_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    weight_override INTEGER,
                    note TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(candidate_id) REFERENCES candidates(id)
                );

                CREATE TABLE IF NOT EXISTS review_drafts (
                    id TEXT PRIMARY KEY,
                    generated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY,
                    place TEXT NOT NULL,
                    industry TEXT NOT NULL,
                    segments_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS official_sources (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    label TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    recommended_by TEXT DEFAULT 'manual',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(mission_id) REFERENCES missions(id)
                );

                CREATE TABLE IF NOT EXISTS retention_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    evidence_hours INTEGER NOT NULL,
                    cloud_log_months INTEGER NOT NULL DEFAULT 3,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS media_assets (
                    id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    captured_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS daily_bundles (
                    id TEXT PRIMARY KEY,
                    bundle_date TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    manifest_json TEXT NOT NULL,
                    cloud_log_status TEXT NOT NULL DEFAULT 'pending',
                    consumed_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS cloud_log_syncs (
                    id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS admin_collection_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS admin_jobs (
                    id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    dry_run INTEGER NOT NULL DEFAULT 0,
                    command_json TEXT NOT NULL,
                    log_path TEXT NOT NULL,
                    started_at TEXT,
                    ended_at TEXT,
                    exit_code INTEGER,
                    error_summary TEXT,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS trash_items (
                    id TEXT PRIMARY KEY,
                    item_type TEXT NOT NULL,
                    reason TEXT,
                    deleted_at TEXT NOT NULL,
                    restore_until TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'trashed',
                    cleanable_after TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def upsert_candidate(self, candidate: Mapping[str, Any]) -> None:
        payload = dict(candidate)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO candidates (
                    id, title, summary, body, source, platform, url, published_at,
                    language, category, score, dedupe_key, payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    summary=excluded.summary,
                    body=excluded.body,
                    source=excluded.source,
                    platform=excluded.platform,
                    url=excluded.url,
                    published_at=excluded.published_at,
                    language=excluded.language,
                    category=excluded.category,
                    score=excluded.score,
                    dedupe_key=excluded.dedupe_key,
                    payload_json=excluded.payload_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    payload["id"],
                    payload.get("title", ""),
                    payload.get("summary", ""),
                    payload.get("body", ""),
                    payload.get("source", ""),
                    payload.get("platform", ""),
                    payload.get("url", ""),
                    payload.get("published_at", ""),
                    payload.get("language", ""),
                    payload.get("category", ""),
                    int(payload.get("score", 0)),
                    payload.get("dedupe_key", ""),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def upsert_candidates(self, candidates: Iterable[Mapping[str, Any]]) -> None:
        for candidate in candidates:
            self.upsert_candidate(candidate)

    def set_human_decision(self, candidate_id: str, status: str, weight_override: Optional[int] = None, note: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO decisions (candidate_id, status, weight_override, note, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    status=excluded.status,
                    weight_override=excluded.weight_override,
                    note=excluded.note,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (candidate_id, status, weight_override, note),
            )

    def save_review_draft(self, draft: Mapping[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO review_drafts (id, generated_at, status, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    generated_at=excluded.generated_at,
                    status=excluded.status,
                    payload_json=excluded.payload_json
                """,
                (
                    draft["id"],
                    draft.get("generated_at", ""),
                    draft.get("status", "draft"),
                    json.dumps(dict(draft), ensure_ascii=False),
                ),
            )

    def list_candidates(self, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self._fetch_candidates(
            """
            SELECT c.payload_json, d.status, d.weight_override, d.note
            FROM candidates c
            LEFT JOIN decisions d ON d.candidate_id = c.id
            ORDER BY c.score DESC, c.published_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return rows

    def list_approved(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._fetch_candidates(
            """
            SELECT c.payload_json, d.status, d.weight_override, d.note
            FROM candidates c
            JOIN decisions d ON d.candidate_id = c.id
            WHERE d.status = 'approved'
            ORDER BY COALESCE(d.weight_override, c.score) DESC, c.published_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    def latest_review_draft(self) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM review_drafts ORDER BY generated_at DESC LIMIT 1"
            ).fetchone()
        return json.loads(row["payload_json"]) if row else {}

    def get_candidate(self, candidate_id: str) -> Dict[str, Any]:
        rows = self._fetch_candidates(
            """
            SELECT c.payload_json, d.status, d.weight_override, d.note
            FROM candidates c
            LEFT JOIN decisions d ON d.candidate_id = c.id
            WHERE c.id = ?
            """,
            (candidate_id,),
        )
        return rows[0] if rows else {}

    def upsert_mission(self, mission_id: str, place: str, industry: str, segments: Iterable[str]) -> None:
        segments_payload = list(segments)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT place, industry, segments_json FROM missions WHERE id = ?",
                (mission_id,),
            ).fetchone()
            changed = False
            if existing:
                changed = (
                    existing["place"] != place
                    or existing["industry"] != industry
                    or json.loads(existing["segments_json"]) != segments_payload
                )
            conn.execute(
                """
                INSERT INTO missions (id, place, industry, segments_json, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    place=excluded.place,
                    industry=excluded.industry,
                    segments_json=excluded.segments_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (mission_id, place, industry, json.dumps(segments_payload, ensure_ascii=False)),
            )
            if changed:
                conn.execute(
                    "UPDATE official_sources SET status = 'needs_review', updated_at = CURRENT_TIMESTAMP WHERE mission_id = ?",
                    (mission_id,),
                )

    def upsert_official_source(
        self,
        source_id: str,
        mission_id: str,
        url: str,
        label: str,
        status: str = "active",
        recommended_by: str = "manual",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO official_sources (id, mission_id, url, label, status, recommended_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    mission_id=excluded.mission_id,
                    url=excluded.url,
                    label=excluded.label,
                    status=excluded.status,
                    recommended_by=excluded.recommended_by,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (source_id, mission_id, url, label, status, recommended_by),
            )

    def list_official_sources(self, mission_id: str = "") -> List[Dict[str, Any]]:
        query = "SELECT * FROM official_sources"
        params: tuple[Any, ...] = ()
        if mission_id:
            query += " WHERE mission_id = ?"
            params = (mission_id,)
        query += " ORDER BY updated_at DESC, label ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def set_retention_hours(self, hours: int, cloud_log_months: Optional[int] = None) -> None:
        evidence_hours = max(1, int(hours))
        current_cloud_months = self.get_cloud_log_months()
        cloud_months = max(1, int(cloud_log_months if cloud_log_months is not None else current_cloud_months))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO retention_settings (id, evidence_hours, cloud_log_months, updated_at)
                VALUES (1, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    evidence_hours=excluded.evidence_hours,
                    cloud_log_months=excluded.cloud_log_months,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (evidence_hours, cloud_months),
            )

    def get_retention_hours(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT evidence_hours FROM retention_settings WHERE id = 1").fetchone()
        return int(row["evidence_hours"]) if row else 48

    def get_cloud_log_months(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT cloud_log_months FROM retention_settings WHERE id = 1").fetchone()
        return int(row["cloud_log_months"]) if row else 3

    def save_daily_bundle(self, bundle: Mapping[str, Any]) -> None:
        payload = dict(bundle)
        manifest = payload.get("manifest_json", {})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_bundles (
                    id, bundle_date, node_id, path, sha256, size_bytes, manifest_json, cloud_log_status, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    bundle_date=excluded.bundle_date,
                    node_id=excluded.node_id,
                    path=excluded.path,
                    sha256=excluded.sha256,
                    size_bytes=excluded.size_bytes,
                    manifest_json=excluded.manifest_json,
                    cloud_log_status=excluded.cloud_log_status,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    payload["id"],
                    payload.get("bundle_date", ""),
                    payload.get("node_id", ""),
                    payload.get("path", ""),
                    payload.get("sha256", ""),
                    int(payload.get("size_bytes", 0)),
                    json.dumps(manifest, ensure_ascii=False),
                    payload.get("cloud_log_status", "pending"),
                ),
            )

    def list_daily_bundles(self, limit: int = 30) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_bundles ORDER BY bundle_date DESC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        bundles = []
        for row in rows:
            payload = dict(row)
            payload["manifest_json"] = json.loads(payload["manifest_json"])
            bundles.append(payload)
        return bundles

    def record_cloud_log_sync(self, sync_id: str, action: str, status: str, payload: Mapping[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cloud_log_syncs (id, action, status, payload_json, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    action=excluded.action,
                    status=excluded.status,
                    payload_json=excluded.payload_json
                """,
                (sync_id, action, status, json.dumps(dict(payload), ensure_ascii=False)),
            )

    def list_cloud_log_syncs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM cloud_log_syncs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        syncs = []
        for row in rows:
            payload = dict(row)
            payload["payload_json"] = json.loads(payload["payload_json"])
            syncs.append(payload)
        return syncs

    def get_admin_collection_config(self) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM admin_collection_config WHERE id = 1").fetchone()
        if row:
            return json.loads(row["payload_json"])
        return {
            "platforms": ["xiaohongshu", "douyin"],
            "manual_queries": ["阳朔 旅游", "阳朔 竹筏", "阳朔 西街"],
            "segments": ["景区", "民宿", "酒店", "旅游餐饮", "旅拍", "骑行", "亲子", "研学", "疗愈"],
            "risk_terms": ["避雷", "排队", "投诉", "宰客", "堵车", "价格"],
            "opportunity_terms": ["攻略", "路线", "新玩法", "小众", "体验", "vlog"],
            "hermes_queries": [],
            "title_target_per_platform": 200,
            "deep_process_limit_per_platform": 40,
            "freshness_window_hours": 24,
            "scroll_rounds_per_query": 8,
            "wait_min_seconds": 25,
            "wait_max_seconds": 60,
            "cooldown_minutes_on_limit": 60,
            "parallel_limit": 2,
        }

    def set_admin_collection_config(self, config: Mapping[str, Any]) -> Dict[str, Any]:
        payload = dict(config)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO admin_collection_config (id, payload_json, updated_at)
                VALUES (1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (json.dumps(payload, ensure_ascii=False),),
            )
        return payload

    def save_admin_job(self, job: Mapping[str, Any]) -> Dict[str, Any]:
        payload = dict(job)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO admin_jobs (
                    id, platform, stage, status, dry_run, command_json, log_path,
                    started_at, ended_at, exit_code, error_summary, payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    platform=excluded.platform,
                    stage=excluded.stage,
                    status=excluded.status,
                    dry_run=excluded.dry_run,
                    command_json=excluded.command_json,
                    log_path=excluded.log_path,
                    started_at=excluded.started_at,
                    ended_at=excluded.ended_at,
                    exit_code=excluded.exit_code,
                    error_summary=excluded.error_summary,
                    payload_json=excluded.payload_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    payload["id"],
                    payload.get("platform", ""),
                    payload.get("stage", ""),
                    payload.get("status", "queued"),
                    1 if payload.get("dry_run") else 0,
                    json.dumps(payload.get("command", []), ensure_ascii=False),
                    payload.get("log_path", ""),
                    payload.get("started_at"),
                    payload.get("ended_at"),
                    payload.get("exit_code"),
                    payload.get("error_summary"),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
        return payload

    def list_admin_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM admin_jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def get_admin_job(self, job_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM admin_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else {}

    def move_to_trash(self, item_type: str, ids: Iterable[str], reason: str = "") -> int:
        now = _utc_now()
        restore_until = _utc_now(days=14)
        moved = 0
        with self._connect() as conn:
            for item_id in ids:
                item = self.get_candidate(item_id) if item_type == "candidate" else {"id": item_id}
                if not item:
                    continue
                conn.execute(
                    """
                    INSERT INTO trash_items (
                        id, item_type, reason, deleted_at, restore_until, cleanable_after,
                        status, payload_json, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 'trashed', ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        item_type=excluded.item_type,
                        reason=excluded.reason,
                        deleted_at=excluded.deleted_at,
                        restore_until=excluded.restore_until,
                        cleanable_after=excluded.cleanable_after,
                        status='trashed',
                        payload_json=excluded.payload_json,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (item_id, item_type, reason, now, restore_until, restore_until, json.dumps(item, ensure_ascii=False)),
                )
                moved += 1
        return moved

    def list_trash(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trash_items WHERE status IN ('trashed', 'cleanable') ORDER BY deleted_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        items = []
        for row in rows:
            payload = dict(row)
            payload["payload_json"] = json.loads(payload["payload_json"])
            items.append(payload)
        return items

    def restore_trash(self, ids: Iterable[str]) -> int:
        restored = 0
        with self._connect() as conn:
            for item_id in ids:
                cursor = conn.execute(
                    "UPDATE trash_items SET status = 'restored', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status IN ('trashed', 'cleanable')",
                    (item_id,),
                )
                restored += cursor.rowcount
        return restored

    def mark_trash_cleanable(self) -> int:
        now = _utc_now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE trash_items
                SET status = 'cleanable', updated_at = CURRENT_TIMESTAMP
                WHERE status = 'trashed' AND cleanable_after <= ?
                """,
                (now,),
            )
        return cursor.rowcount

    def _fetch_candidates(self, query: str, params: tuple[Any, ...]) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        candidates = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            status = row["status"] or "pending"
            weight_override = row["weight_override"]
            payload["human_status"] = status
            payload["human_note"] = row["note"] or ""
            if weight_override is not None:
                payload["score"] = int(weight_override)
                payload["weight_override"] = int(weight_override)
            candidates.append(payload)
        return candidates

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _utc_now(days: int = 0) -> str:
    now = datetime.now(timezone.utc)
    if days:
        from datetime import timedelta

        now = now + timedelta(days=days)
    return now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
