"""SQLite storage for candidates, review drafts, and human decisions."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


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

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
