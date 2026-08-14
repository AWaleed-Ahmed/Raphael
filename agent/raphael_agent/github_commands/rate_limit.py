"""Per repo+actor command rate limit (GH-053). Default 10/hour."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from raphael_agent.timeutil import utc_now


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        raw = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class CommandRateLimiter:
    """Durable sliding window: ``limit`` events per ``window`` per repo+actor."""

    def __init__(
        self,
        path: Path,
        *,
        limit: int = 10,
        window: timedelta | None = None,
        now_fn: Callable[[], str] | None = None,
    ) -> None:
        self.path = path
        self.limit = max(1, int(limit))
        self.window = window or timedelta(hours=1)
        self.now_fn = now_fn or utc_now
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, list[str]]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        out: dict[str, list[str]] = {}
        for key, stamps in data.items():
            if isinstance(stamps, list):
                out[str(key)] = [str(s) for s in stamps]
        return out

    def _save(self, data: dict[str, list[str]]) -> None:
        self.path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def key(owner: str, repo: str, actor: str) -> str:
        return f"{owner}/{repo}|{actor}"

    def allow(self, owner: str, repo: str, actor: str) -> tuple[bool, int]:
        """Record an attempt if under the limit. Returns (allowed, remaining_after)."""
        now = self.now_fn()
        now_dt = _parse_ts(now) or datetime.now(timezone.utc)
        cutoff = now_dt - self.window
        bucket = self.key(owner, repo, actor)
        with self._lock:
            data = self._load()
            stamps = [
                s
                for s in data.get(bucket, [])
                if (parsed := _parse_ts(s)) is not None and parsed >= cutoff
            ]
            if len(stamps) >= self.limit:
                data[bucket] = stamps
                self._save(data)
                return False, 0
            stamps.append(now)
            data[bucket] = stamps
            self._save(data)
            return True, self.limit - len(stamps)
