"""Optional SQLite-backed RunStore (stdlib sqlite3).

Enable with ``RAPHAEL_AGENT_STORE=sqlite``. Default remains JSON documents.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterator

from raphael_agent.store.run_store import RunStore, default_data_dir


class SqliteRunStore(RunStore):
    """SQLite implementation with the same caller-facing methods as RunStore."""

    def __init__(self, root: Path | None = None, db_path: Path | None = None) -> None:
        self.root = root or default_data_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self.runs_dir = self.root / "runs"
        self.raw_dir = self.root / "raw_events"
        self.decisions_path = self.root / "ingest_decisions.jsonl"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or (
            Path(os.environ["RAPHAEL_AGENT_SQLITE_PATH"])
            if os.environ.get("RAPHAEL_AGENT_SQLITE_PATH")
            else self.root / "runs.sqlite3"
        )
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS runs (
                        run_id TEXT PRIMARY KEY,
                        fingerprint TEXT,
                        tenant_id TEXT,
                        status TEXT,
                        updated_at TEXT,
                        payload TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS decisions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        decided_at TEXT,
                        payload TEXT NOT NULL
                    )
                    """
                )
                conn.commit()

    def save_run(self, run: dict[str, Any]) -> None:
        run_id = run["run_id"]
        payload = json.dumps(run, default=str)
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO runs(run_id, fingerprint, tenant_id, status, updated_at, payload)
                    VALUES(?,?,?,?,?,?)
                    ON CONFLICT(run_id) DO UPDATE SET
                      fingerprint=excluded.fingerprint,
                      tenant_id=excluded.tenant_id,
                      status=excluded.status,
                      updated_at=excluded.updated_at,
                      payload=excluded.payload
                    """,
                    (
                        run_id,
                        run.get("failure_fingerprint"),
                        run.get("tenant_id"),
                        run.get("status"),
                        run.get("updated_at"),
                        payload,
                    ),
                )
                conn.commit()
            # Mirror JSON doc for operators inspecting the data dir.
            super().save_run(run)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT payload FROM runs WHERE run_id = ?", (run_id,)
                ).fetchone()
        if row is None:
            return super().get_run(run_id)
        return json.loads(row["payload"])

    def iter_runs(self) -> Iterator[dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT payload FROM runs ORDER BY updated_at ASC"
                ).fetchall()
        if not rows:
            yield from super().iter_runs()
            return
        for row in rows:
            try:
                yield json.loads(row["payload"])
            except json.JSONDecodeError:
                continue

    def append_decision(self, decision: dict[str, Any]) -> None:
        super().append_decision(decision)
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO decisions(decided_at, payload) VALUES(?, ?)",
                    (decision.get("decided_at"), json.dumps(decision, default=str)),
                )
                conn.commit()


def open_run_store(root: Path | None = None) -> RunStore:
    """Factory: JSON (default) or SQLite when RAPHAEL_AGENT_STORE=sqlite."""
    mode = os.environ.get("RAPHAEL_AGENT_STORE", "json").strip().lower()
    if mode in {"sqlite", "sql", "db"}:
        return SqliteRunStore(root=root)
    return RunStore(root=root)
