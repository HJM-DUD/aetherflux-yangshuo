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
