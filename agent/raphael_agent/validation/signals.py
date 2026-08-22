"""Provider-neutral correctness signals used by sandbox validation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx


def _path(value: Any, path: str) -> Any:
    current = value
    for token in path.split(".") if path else []:
        if isinstance(current, dict):
            current = current.get(token)
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            return None
    return current


def _checksum(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _check(spec: dict[str, Any], *, status: str, message: str, exit_code: int = 0) -> dict[str, Any]:
    return {
        "name": str(spec.get("name") or spec.get("type") or "correctness_signal"),
        "kind": "repository_test",
        "status": status,
        "mandatory": bool(spec.get("mandatory", True)),
        "duration_ms": 0,
        "exit_code": exit_code,
        "message": message[:1000],
        "artifact_refs": [],
    }


def _replay(spec: dict[str, Any]) -> dict[str, Any]:
    url = str(spec.get("url") or "")
    if not url:
        return _check(spec, status="unavailable", message="http_replay requires url", exit_code=2)
    method = str(spec.get("method") or "GET").upper()
    try:
        response = httpx.request(
            method, url,
            headers={str(k): str(v) for k, v in (spec.get("headers") or {}).items()},
            json=spec.get("json_body") if "json_body" in spec else None,
            content=spec.get("body"),
            timeout=float(spec.get("timeout_seconds") or 20),
        )
    except Exception as exc:  # noqa: BLE001 - unavailable signal is explicit
        return _check(spec, status="unavailable", message=f"request replay unavailable: {exc}", exit_code=2)
    expected = spec.get("expected_status", 200)
    body = response.text[:10000]
    pattern = spec.get("expected_body_pattern")
    ok = response.status_code == int(expected) and (not pattern or str(pattern) in body)
    return _check(spec, status="passed" if ok else "failed", message=f"status={response.status_code} body_match={not pattern or str(pattern) in body}", exit_code=0 if ok else 1)


def evaluate_validation_signals(
    signals: list[dict[str, Any]],
    *,
    baseline: dict[str, Any] | None = None,
    current: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate correctness signals without making assumptions about a provider."""
    baseline = baseline or {}
    current = current or {}
    checks: list[dict[str, Any]] = []
    for spec in signals:
        kind = str(spec.get("type") or "").lower()
        if kind == "http_replay":
            checks.append(_replay(spec))
            continue
        if kind in {"business_invariant", "api_contract"}:
            actual = _path(current, str(spec.get("path") or ""))
            expected = spec.get("expected")
            ok = actual == expected if "expected" in spec else actual is not None
            checks.append(_check(spec, status="passed" if ok else "failed", message=f"path={spec.get('path')} actual={actual!r} expected={expected!r}", exit_code=0 if ok else 1))
            continue
        if kind == "checksum":
            actual = _checksum(_path(current, str(spec.get("path") or "")))
            expected = str(spec.get("expected_checksum") or _checksum(_path(baseline, str(spec.get("path") or ""))))
            ok = actual == expected
            checks.append(_check(spec, status="passed" if ok else "failed", message=f"checksum_match={ok}", exit_code=0 if ok else 1))
            continue
        if kind == "queue_side_effect":
            before = float(_path(baseline, str(spec.get("count_path") or "count")) or 0)
            after = float(_path(current, str(spec.get("count_path") or "count")) or 0)
            delta = after - before
            minimum = float(spec.get("minimum_delta") or 1)
            ok = delta >= minimum
            checks.append(_check(spec, status="passed" if ok else "failed", message=f"delta={delta} minimum={minimum}", exit_code=0 if ok else 1))
            continue
        if kind == "golden_trace":
            expected = [str(item) for item in (spec.get("expected_spans") or baseline.get("span_sequence") or [])]
            actual = [str(item.get("name") if isinstance(item, dict) else item) for item in (current.get("span_sequence") or [])]
            ok = actual[:len(expected)] == expected and (not spec.get("require_same_length") or len(actual) == len(expected))
            checks.append(_check(spec, status="passed" if ok else "failed", message=f"expected_spans={expected} actual_spans={actual}", exit_code=0 if ok else 1))
            continue
        if kind == "slo":
            actual = float(_path(current, str(spec.get("path") or "value")) or 0)
            threshold = float(spec.get("max") if spec.get("max") is not None else spec.get("min") or 0)
            ok = actual <= threshold if spec.get("max") is not None else actual >= threshold
            checks.append(_check(spec, status="passed" if ok else "failed", message=f"value={actual} threshold={threshold}", exit_code=0 if ok else 1))
            continue
        checks.append(_check(spec, status="unavailable", message=f"unsupported correctness signal: {kind}", exit_code=2))
    return checks
