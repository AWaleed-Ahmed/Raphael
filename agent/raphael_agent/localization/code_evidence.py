"""Provider-neutral code coverage and dependency evidence adapters."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def load_coverage(workspace: str | Path | None) -> dict[str, dict[int, int]]:
    """Read coverage.py JSON or LCOV files when present.

    Returns relative file -> line -> hit count. Missing/unreadable reports are
    represented by an empty mapping and never block localization.
    """
    if not workspace:
        return {}
    root = Path(workspace)
    reports = [root / "coverage.json", root / ".coverage.json", root / "coverage" / "coverage.json"]
    for report in reports:
        if not report.is_file():
            continue
        try:
            payload = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        files = payload.get("files") if isinstance(payload, dict) else None
        if not isinstance(files, dict):
            continue
        result: dict[str, dict[int, int]] = {}
        for raw_path, data in files.items():
            if not isinstance(data, dict):
                continue
            lines = data.get("executed_lines") or data.get("lines") or []
            if isinstance(lines, dict):
                result[_normalize_path(str(raw_path))] = {int(k): int(v or 0) for k, v in lines.items() if str(k).isdigit()}
            elif isinstance(lines, list):
                result[_normalize_path(str(raw_path))] = {int(line): 1 for line in lines if isinstance(line, int) or str(line).isdigit()}
        return result
    lcov = root / "lcov.info"
    if lcov.is_file():
        result: dict[str, dict[int, int]] = {}
        current: str | None = None
        try:
            lines = lcov.read_text(encoding="utf-8").splitlines()
        except OSError:
            return {}
        for line in lines:
            if line.startswith("SF:"):
                current = _normalize_path(line[3:])
                result.setdefault(current, {})
            elif current and line.startswith("DA:"):
                parts = line[3:].split(",", 1)
                if len(parts) == 2 and parts[0].isdigit():
                    result[current][int(parts[0])] = int(float(parts[1]))
            elif line == "end_of_record":
                current = None
        return result
    return {}


def coverage_relevance(coverage: dict[str, dict[int, int]], path: str, line: int) -> float:
    """Return a bounded execution signal for a candidate line."""
    normalized = _normalize_path(path)
    matching = coverage.get(normalized)
    if matching is None:
        matching = next((v for key, v in coverage.items() if normalized.endswith("/" + key) or key.endswith("/" + normalized)), None)
    if not matching:
        return 0.0
    hits = int(matching.get(int(line), 0))
    return 1.0 if hits > 0 else 0.0


_IMPORT_RE = re.compile(r"^\s*(?:from\s+([\w.]+)|import\s+([\w.]+))", re.M)
_JS_IMPORT_RE = re.compile(r"(?:from|require\()\s*[\"']([^\"']+)", re.M)


def build_dependency_graph(workspace: str | Path | None) -> dict[str, set[str]]:
    """Build a lightweight Python/JS dependency graph from source imports."""
    if not workspace:
        return {}
    root = Path(workspace)
    graph: dict[str, set[str]] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".py", ".js", ".jsx", ".ts", ".tsx"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        imports: set[str] = set()
        if path.suffix.lower() == ".py":
            for match in _IMPORT_RE.finditer(text):
                imports.add(match.group(1) or match.group(2))
        else:
            imports.update(match.group(1) for match in _JS_IMPORT_RE.finditer(text))
        graph[rel] = imports
    return graph


def dependency_relevance(graph: dict[str, set[str]], candidate_path: str, anchor_path: str) -> float:
    """Return 1 for direct dependency/caller relationships, 0.5 for proximity."""
    candidate = _normalize_path(candidate_path)
    anchor = _normalize_path(anchor_path)
    if candidate == anchor:
        return 1.0
    imports = graph.get(candidate, set())
    if any(candidate.endswith(str(item).replace(".", "/")) or anchor.endswith(str(item).replace(".", "/")) for item in imports):
        return 1.0
    if candidate.rsplit("/", 1)[0] == anchor.rsplit("/", 1)[0]:
        return 0.5
    return 0.0
