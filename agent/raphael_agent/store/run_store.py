"""Durable JSON document store for agent run_records and ingest decisions."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Iterator


def default_data_dir() -> Path:
    raw = os.environ.get("RAPHAEL_AGENT_DATA_DIR")
    if raw:
        return Path(raw)
    return Path.cwd() / ".raphael-agent-data"


class RunStore:
    """Filesystem-backed store (JSON docs). Swap to SQLite later without changing callers."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_data_dir()
        self.runs_dir = self.root / "runs"
        self.raw_dir = self.root / "raw_events"
        self.decisions_path = self.root / "ingest_decisions.jsonl"
        self._lock = threading.RLock()
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)

    def _run_path(self, run_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in run_id)
        return self.runs_dir / f"{safe}.json"

    def save_run(self, run: dict[str, Any]) -> None:
        run_id = run["run_id"]
        path = self._run_path(run_id)
        with self._lock:
            path.write_text(json.dumps(run, indent=2, default=str) + "\n", encoding="utf-8")

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        path = self._run_path(run_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def iter_runs(self) -> Iterator[dict[str, Any]]:
        with self._lock:
            paths = sorted(self.runs_dir.glob("*.json"))
        for path in paths:
            try:
                yield json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

    def list_runs(self) -> list[dict[str, Any]]:
        return list(self.iter_runs())

    def save_raw_event(self, event_id: str, payload: dict[str, Any] | bytes | str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in event_id)[:120]
        path = self.raw_dir / f"{safe}.json"
        with self._lock:
            if isinstance(payload, (bytes, bytearray)):
                path.write_bytes(bytes(payload))
            elif isinstance(payload, str):
                path.write_text(payload, encoding="utf-8")
            else:
                path.write_text(
                    json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
                )
        return str(path)

    def append_decision(self, decision: dict[str, Any]) -> None:
        line = json.dumps(decision, default=str)
        with self._lock:
            with self.decisions_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def find_by_fingerprint(
        self,
        fingerprint: str,
        *,
        statuses: set[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return the newest matching run for a fingerprint (optional status filter)."""
        matches: list[dict[str, Any]] = []
        for run in self.iter_runs():
            if run.get("failure_fingerprint") != fingerprint:
                continue
            if statuses is not None and run.get("status") not in statuses:
                continue
            matches.append(run)
        if not matches:
            return None
        matches.sort(key=lambda r: r.get("updated_at") or r.get("created_at") or "")
        return matches[-1]

    def count_active(self, tenant_id: str) -> int:
        active = {"pending", "running"}
        return sum(
            1
            for run in self.iter_runs()
            if run.get("tenant_id") == tenant_id and run.get("status") in active
        )
