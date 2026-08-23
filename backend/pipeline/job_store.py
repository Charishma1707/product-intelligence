"""
pipeline/job_store.py — SQLite-backed job persistence for the LangGraph pipeline.

Stores serialized ProductState per job_id so that:
  - HITL-paused jobs survive server restarts
  - The /resume endpoint can reload and continue frozen state
  - Job history is available for monitoring

Tables:
  jobs(
    job_id TEXT PRIMARY KEY,
    brand TEXT, mpn TEXT,
    status TEXT,
    overall_confidence REAL,
    created_at TEXT,
    updated_at TEXT,
    state_json TEXT          -- Full serialized ProductState
  )
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from enum import Enum
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.state import PipelineState

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).resolve().parent.parent / "job_store.db"


# ---------------------------------------------------------------------------
# DB init
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_number       INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id           TEXT UNIQUE NOT NULL,
                brand            TEXT NOT NULL,
                mpn              TEXT NOT NULL,
                status           TEXT NOT NULL,
                overall_confidence REAL,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL,
                state_json       TEXT NOT NULL
            )
        """)
        conn.commit()
    logger.info("Job store initialized at %s", _DB_PATH)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def save_job(state: PipelineState) -> None:
    """Upsert the full PipelineState into the jobs table."""
    now = datetime.now(timezone.utc).isoformat()
    job_id = state.get("job_id") or state.get("product_id")
    if not job_id:
        import uuid
        job_id = str(uuid.uuid4())
        state["job_id"] = job_id

    # Check if it already exists
    with _get_conn() as conn:
        existing = conn.execute(
            "SELECT created_at FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        created_at = existing["created_at"] if existing else now

        def custom_serializer(obj):
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            elif hasattr(obj, "__dict__"):
                return obj.__dict__
            elif isinstance(obj, Enum):
                return obj.value
            return str(obj)

        conn.execute("""
            INSERT INTO jobs (job_id, brand, mpn, status, overall_confidence, created_at, updated_at, state_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                status             = excluded.status,
                overall_confidence = excluded.overall_confidence,
                updated_at         = excluded.updated_at,
                state_json         = excluded.state_json
        """, (
            job_id,
            state.get("brand", ""),
            state.get("mpn", ""),
            state.get("status", "running"),
            state.get("overall_confidence", 0.0),
            created_at,
            now,
            json.dumps(state, default=custom_serializer),
        ))
        conn.commit()
    logger.debug("Job saved: %s (%s)", job_id, state.get("status"))


def load_job(job_id: str) -> PipelineState | None:
    """Load and deserialize a PipelineState from the jobs table."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT state_json FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()

    if not row:
        return None

    return json.loads(row["state_json"])


def list_jobs(status: str | None = None, limit: int = 50) -> list[dict]:
    """Return summary rows from the jobs table."""
    with _get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT job_number, job_id, brand, mpn, status, overall_confidence, created_at, updated_at "
                "FROM jobs WHERE status = ? ORDER BY job_number ASC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT job_number, job_id, brand, mpn, status, overall_confidence, created_at, updated_at "
                "FROM jobs ORDER BY job_number ASC LIMIT ?",
                (limit,),
            ).fetchall()

    return [dict(r) for r in rows]


def delete_job(job_id: str) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        conn.commit()
    return cursor.rowcount > 0
