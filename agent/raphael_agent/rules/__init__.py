"""Preset / derived fix rules for Route B (labeled Issues)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from raphael_agent.patch.config import allowlist_prefixes
from raphael_agent.schema_util import validate_agent
from raphael_agent.timeutil import utc_now

__all__ = [
    "load_or_derive_fix_rules",
    "intersect_writable_prefixes",
    "PRESET_RELATIVE_PATH",
    "DERIVE_CANDIDATES",
]

PRESET_RELATIVE_PATH = ".raphael/issue-fix.yaml"
DERIVE_CANDIDATES: tuple[str, ...] = (
    ".raphael/config.yaml",
    ".raphael/config.yml",
    "CONTRIBUTING.md",
    "CODEOWNERS",
    ".github/CODEOWNERS",
)

_MAX_DERIVE_FILES = 4
_MAX_FILE_BYTES = 12_000
_PREFIX_RE = re.compile(
    r"(?im)^\s*(?:writable[_-]?paths?|allowlist|paths?)\s*[:=]\s*(.+)$"
)


def intersect_writable_prefixes(requested: list[str]) -> list[str]:
    """Intersect requested prefixes with the global patch allowlist (cannot widen)."""
    global_prefixes = allowlist_prefixes()
    out: list[str] = []
    for raw in requested:
        prefix = str(raw).replace("\\", "/").strip().lstrip("/")
        if not prefix:
            continue
        if not prefix.endswith("/"):
            prefix = prefix + "/"
        for allowed in global_prefixes:
            if prefix.startswith(allowed) or allowed.startswith(prefix):
                # Keep the more specific intersection under global ceiling.
                chosen = prefix if prefix.startswith(allowed) else allowed
                if chosen not in out:
                    out.append(chosen)
                break
    return out or list(global_prefixes)


def _parse_simple_yaml_like(text: str) -> dict[str, Any]:
    """Minimal parser for our small issue-fix.yaml shape (no PyYAML required)."""
    result: dict[str, Any] = {
        "writable_path_prefixes": [],
        "must": [],
        "must_not": [],
        "test_commands": [],
        "notes": "",
    }
    current_list: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        list_key = None
        for key in ("writable_path_prefixes", "must", "must_not", "test_commands"):
            if stripped.startswith(f"{key}:") or stripped == f"{key}:":
                list_key = key
                break
        if list_key:
            current_list = list_key
            remainder = stripped.split(":", 1)[1].strip()
            if remainder.startswith("[") and remainder.endswith("]"):
                inner = remainder[1:-1].strip()
                if inner:
                    result[list_key] = [
                        p.strip().strip("'\"") for p in inner.split(",") if p.strip()
                    ]
                current_list = None
            continue
        if stripped.startswith("notes:"):
            current_list = None
            result["notes"] = stripped.split(":", 1)[1].strip().strip("'\"")
            continue
        if stripped.startswith("- ") and current_list:
            result[current_list].append(stripped[2:].strip().strip("'\""))
    return result


def _read_bounded(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        data = path.read_bytes()[:_MAX_FILE_BYTES]
        return data.decode("utf-8", errors="replace")
    except OSError:
        return None


def _derive_from_texts(paths_and_text: list[tuple[str, str]]) -> dict[str, Any]:
    prefixes: list[str] = []
    must: list[str] = []
    must_not = [
        "Do not introduce secrets or credentials",
        "Do not weaken securityContext, probes required by policy, or NetworkPolicy",
        "Do not modify files outside writable_path_prefixes",
    ]
    notes_parts: list[str] = []
    for rel, text in paths_and_text:
        notes_parts.append(f"read:{rel}")
        for match in _PREFIX_RE.finditer(text):
            chunk = match.group(1).strip().strip("'\"")
            for part in re.split(r"[,;\s]+", chunk):
                part = part.strip().strip("'\"")
                if part and ("/" in part or part.endswith("/")):
                    prefixes.append(part)
        # Capture short must-like bullets from CONTRIBUTING
        if rel.endswith("CONTRIBUTING.md"):
            for line in text.splitlines():
                s = line.strip()
                if s.startswith("- ") and len(s) < 160:
                    must.append(s[2:].strip())
                    if len(must) >= 8:
                        break
    if not prefixes:
        prefixes = list(allowlist_prefixes())
    return {
        "source": "derived",
        "source_paths": [p for p, _ in paths_and_text],
        "writable_path_prefixes": intersect_writable_prefixes(prefixes),
        "must": must[:12],
        "must_not": must_not,
        "test_commands": [],
        "notes": "Derived from bounded repo files: " + ", ".join(notes_parts),
        "created_at": utc_now(),
    }


def load_or_derive_fix_rules(workspace: Path | str | None) -> dict[str, Any]:
    """Load `.raphael/issue-fix.yaml` or derive rules from bounded repo files."""
    root = Path(workspace) if workspace else None
    if root and root.is_dir():
        preset = root / PRESET_RELATIVE_PATH
        text = _read_bounded(preset)
        if text is not None:
            parsed = _parse_simple_yaml_like(text)
            rules = {
                "source": "preset",
                "source_paths": [PRESET_RELATIVE_PATH],
                "writable_path_prefixes": intersect_writable_prefixes(
                    list(parsed.get("writable_path_prefixes") or [])
                    or list(allowlist_prefixes())
                ),
                "must": list(parsed.get("must") or []),
                "must_not": list(parsed.get("must_not") or [])
                or [
                    "Do not introduce secrets or credentials",
                    "Do not modify files outside writable_path_prefixes",
                ],
                "test_commands": list(parsed.get("test_commands") or []),
                "notes": parsed.get("notes") or "Loaded from .raphael/issue-fix.yaml",
                "created_at": utc_now(),
            }
            validate_agent("fix_rules.json", rules)
            return rules

        collected: list[tuple[str, str]] = []
        for rel in DERIVE_CANDIDATES:
            if len(collected) >= _MAX_DERIVE_FILES:
                break
            content = _read_bounded(root / rel)
            if content is not None:
                collected.append((rel, content))
        if collected:
            rules = _derive_from_texts(collected)
            validate_agent("fix_rules.json", rules)
            return rules

    # No workspace files — still emit rules under global allowlist ceiling.
    rules = {
        "source": "derived",
        "source_paths": [],
        "writable_path_prefixes": list(allowlist_prefixes()),
        "must": [],
        "must_not": [
            "Do not introduce secrets or credentials",
            "Do not modify files outside writable_path_prefixes",
        ],
        "test_commands": [],
        "notes": "No repo rule files found; using global patch allowlist only",
        "created_at": utc_now(),
    }
    validate_agent("fix_rules.json", rules)
    return rules
