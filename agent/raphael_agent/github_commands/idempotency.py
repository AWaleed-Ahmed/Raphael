"""Idempotent command handling via comment_id / delivery id (GH-054)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class CommandIdempotencyStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")

    @staticmethod
    def keys(*, comment_id: str | None, delivery_id: str | None) -> list[str]:
        out: list[str] = []
        if comment_id:
            out.append(f"comment:{comment_id}")
        if delivery_id:
            out.append(f"delivery:{delivery_id}")
        return out

    def get(
        self, *, comment_id: str | None, delivery_id: str | None
    ) -> dict[str, Any] | None:
        keys = self.keys(comment_id=comment_id, delivery_id=delivery_id)
        if not keys:
            return None
        with self._lock:
            data = self._load()
        for key in keys:
            value = data.get(key)
            if isinstance(value, dict):
                return dict(value)
        return None

    def put(
        self,
        result: dict[str, Any],
        *,
        comment_id: str | None,
        delivery_id: str | None,
    ) -> None:
        keys = self.keys(comment_id=comment_id, delivery_id=delivery_id)
        if not keys:
            return
        stored = dict(result)
        with self._lock:
            data = self._load()
            for key in keys:
                data[key] = stored
            self._save(data)
