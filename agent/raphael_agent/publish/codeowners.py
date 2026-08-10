"""CODEOWNERS → reviewer login extraction (Option B hardening)."""

from __future__ import annotations

import os
import re
from pathlib import Path

_OWNER_RE = re.compile(r"@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}[A-Za-z0-9])?)")


def _candidate_paths(workspace: Path | None) -> list[Path]:
    roots: list[Path] = []
    if workspace is not None:
        roots.append(workspace)
    env_root = os.environ.get("RAPHAEL_CODEOWNERS_WORKSPACE", "").strip()
    if env_root:
        roots.append(Path(env_root))
    rels = ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")
    out: list[Path] = []
    for root in roots:
        for rel in rels:
            path = root / rel
            if path.is_file():
                out.append(path)
    explicit = os.environ.get("RAPHAEL_CODEOWNERS_PATH", "").strip()
    if explicit and Path(explicit).is_file():
        out.insert(0, Path(explicit))
    return out


def parse_codeowners_logins(text: str) -> list[str]:
    """Return unique user logins (not teams) from CODEOWNERS contents."""
    logins: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Skip team refs like @org/team — keep simple user @login only.
        for match in _OWNER_RE.finditer(stripped):
            login = match.group(1)
            # Heuristic: team paths contain '/' after @org/
            span = match.span()
            before = stripped[max(0, span[0] - 1) : span[0]]
            after = stripped[span[1] : span[1] + 1]
            if after == "/":
                continue
            if login not in logins:
                logins.append(login)
            if before:  # silence unused
                pass
    return logins


def reviewers_from_codeowners(workspace: Path | str | None = None) -> list[str]:
    root = Path(workspace) if workspace else None
    for path in _candidate_paths(root):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        logins = parse_codeowners_logins(text)
        if logins:
            return logins
    return []
