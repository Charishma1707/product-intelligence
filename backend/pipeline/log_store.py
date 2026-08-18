"""
pipeline/log_store.py — Structured SQLite log database.

Every pipeline node writes a log entry here with full context.
This makes it possible to:
  - Replay exactly what happened in any job
  - Show the human a clean audit trail
  - Export logs for the hackathon judges
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOG_DB = Path(__file__).resolve().parent.parent / "logs" / "pipeline_logs.db"

logger = logging.getLogger(__name__)

# ANSI color codes for terminal output
_C = {
    "reset":  "\033[0m",
    "bold":   "\033[1m",
    "blue":   "\033[34m",
    "cyan":   "\033[36m",
    "green":  "\033[32m",
    "yellow": "\033[33m",
    "red":    "\033[31m",
    "white":  "\033[37m",
    "gray":   "\033[90m",
    "bg_blue": "\033[44m",
}


def _get_conn() -> sqlite3.Connection:
    _LOG_DB.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(_LOG_DB))
    conn.row_factory = sqlite3.Row
    return conn


def init_log_db() -> None:
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                node        TEXT NOT NULL,
                level       TEXT NOT NULL DEFAULT 'INFO',
                message     TEXT NOT NULL,
                details_json TEXT
            )
        """)
        conn.commit()


def write_log(job_id: str, node: str, message: str, level: str = "INFO", details: Any = None) -> None:
    """Write a structured log entry for a pipeline step."""
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO logs (job_id, timestamp, node, level, message, details_json) VALUES (?,?,?,?,?,?)",
                (
                    job_id,
                    datetime.now(timezone.utc).isoformat(),
                    node,
                    level,
                    message,
                    json.dumps(details) if details else None,
                ),
            )
            conn.commit()
    except Exception as e:
        logger.warning("Log write failed: %s", e)


def get_logs(job_id: str) -> list[dict]:
    """Return all log entries for a job."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM logs WHERE job_id = ? ORDER BY id ASC", (job_id,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def print_job_logs(job_id: str) -> None:
    """Print a beautiful colored audit trail for a job to the terminal."""
    logs = get_logs(job_id)
    if not logs:
        print(f"{_C['gray']}  No logs found for job {job_id}{_C['reset']}")
        return

    level_color = {"INFO": _C["cyan"], "WARNING": _C["yellow"], "ERROR": _C["red"], "SUCCESS": _C["green"]}
    node_width = max((len(r["node"]) for r in logs), default=10)

    print(f"\n{_C['bold']}{_C['blue']}  AUDIT TRAIL — {job_id}{_C['reset']}")
    print(f"  {_C['gray']}{'-'*80}{_C['reset']}")

    for row in logs:
        ts = row["timestamp"][11:19]  # HH:MM:SS
        node = row["node"].ljust(node_width)
        lvl = row["level"]
        color = level_color.get(lvl, _C["white"])
        msg = row["message"]
        print(f"  {_C['gray']}{ts}{_C['reset']}  {color}{node}{_C['reset']}  {msg}")

    print(f"  {_C['gray']}{'-'*80}{_C['reset']}")


# Initialize on import
try:
    init_log_db()
except Exception:
    pass
