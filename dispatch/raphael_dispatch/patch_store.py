"""Ephemeral in-memory store for raw rendered manifests during patching."""

from __future__ import annotations

import threading
from typing import Any


class EphemeralPatchStore:
    """Short-lived, patch-only staging store excluded from durable RunStore.

    Maintains raw, unredacted manifest files disclosed by connector deploy_revision
    responses so deterministic patch templates can perform line-level splices without
    persisting secret-bearing manifest content to disk or leaking it to diagnosis.
    """

    def __init__(self) -> None:
        self._store: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def save_manifests(self, job_id: str, files: list[dict[str, Any]]) -> None:
        """Store or overwrite raw rendered manifests for a job."""
        with self._lock:
            self._store[job_id] = [dict(item) for item in files if isinstance(item, dict)]

    def get_manifests(self, job_id: str) -> list[dict[str, Any]]:
        """Retrieve raw manifests for patch generation."""
        with self._lock:
            manifests = self._store.get(job_id)
            return [dict(item) for item in manifests] if manifests is not None else []

    def has_manifests(self, job_id: str) -> bool:
        """Check if manifests are currently staged for a job."""
        with self._lock:
            return job_id in self._store

    def purge(self, job_id: str) -> None:
        """Purge ephemeral manifests at terminal cleanup."""
        with self._lock:
            self._store.pop(job_id, None)
