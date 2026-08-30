"""Deterministic fix templates for high-confidence known patterns (FR-045)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _manifest_dir(run: dict[str, Any]) -> Path | None:
    workspace = run.get("workspace_path")
    if not workspace:
        return None
    root = Path(workspace)
    rel = (run.get("manifests") or {}).get("path") or "deploy/manifests"
    target = root / rel
    if target.is_dir():
        return target
    if target.is_file():
        return target.parent
    return None


def _iter_yaml_files(directory: Path) -> list[Path]:
    return sorted(
        p
        for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in {".yaml", ".yml"}
    )


def _manifest_sources(run: dict[str, Any]) -> list[tuple[str, str]] | None:
    """Return [(relative_path, content)] for the manifests to fix.

    Prefers ``run["rendered_files"]`` — the files the connector actually rendered
    and applied, disclosed by the deploy_revision response (contracts-v1.1.0). This
    lets the deterministic templates operate in the dispatch path without touching
    the customer filesystem. Falls back to reading the local workspace for
    in-process runs that still set ``workspace_path``.
    """
    rendered = run.get("rendered_files")
    if isinstance(rendered, list) and rendered:
        sources: list[tuple[str, str]] = []
        for item in rendered:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            content = item.get("content")
            if isinstance(path, str) and isinstance(content, str) and path.lower().endswith(
                (".yaml", ".yml")
            ):
                sources.append((path, content))
        return sources or None

    directory = _manifest_dir(run)
    if directory is None:
        return None
    workspace = run.get("workspace_path")
    root = Path(workspace) if workspace else directory
    sources = []
    for path in _iter_yaml_files(directory):
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            rel = path.as_posix()
        sources.append((rel, path.read_text(encoding="utf-8")))
    return sources or None


def fix_probe_port_mismatch(run: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Align readinessProbe.httpGet.port with containerPort in broken manifests."""
    sources = _manifest_sources(run)
    if sources is None:
        return None
    files: list[dict[str, Any]] = []
    for rel, original in sources:
        # Only rewrite when containerPort and readiness probe port disagree.
        match = re.search(
            r"(containerPort:\s*)(\d+)([\s\S]{0,500}?readinessProbe:[\s\S]{0,200}?port:\s*)(\d+)",
            original,
            re.I,
        )
        if not match:
            continue
        cport, pport = match.group(2), match.group(4)
        if cport == pport:
            continue
        fixed = (
            original[: match.start(4)]
            + cport
            + original[match.end(4) :]
        )
        if fixed == original:
            continue
        files.append(
            {
                "path": rel,
                "action": "modify",
                "content": fixed,
                "unified_diff_hunk": (
                    f"--- a/{rel}\n+++ b/{rel}\n"
                    f"@@ readinessProbe.port @@\n-{pport}\n+{cport}\n"
                ),
            }
        )
    return files or None


def fix_bad_image(run: dict[str, Any], *, known_good: str = "hashicorp/http-echo:1.0") -> list[dict[str, Any]] | None:
    sources = _manifest_sources(run)
    if sources is None:
        return None
    files: list[dict[str, Any]] = []
    for rel, original in sources:
        if "does-not-exist" not in original and "ImagePullBackOff" not in original:
            # Still try common bad tag pattern in image: lines
            if not re.search(r"image:\s*\S+:(does-not-exist|missing|invalid)\b", original):
                continue
        fixed, n = re.subn(
            r"(image:\s*)(\S+)",
            lambda m: f"{m.group(1)}{known_good}"
            if "does-not-exist" in m.group(2)
            or m.group(2).endswith(":missing")
            or m.group(2).endswith(":invalid")
            else m.group(0),
            original,
            count=1,
        )
        if n == 0 or fixed == original:
            continue
        files.append(
            {
                "path": rel,
                "action": "modify",
                "content": fixed,
                "unified_diff_hunk": None,
            }
        )
    return files or None


def fix_missing_configmap_key(run: dict[str, Any]) -> list[dict[str, Any]] | None:
    sources = _manifest_sources(run)
    if sources is None:
        return None
    files: list[dict[str, Any]] = []
    for rel, original in sources:
        if "key: DATABASE_URL" not in original:
            continue
        if re.search(r"(?m)^  DATABASE_URL:", original):
            continue
        # Add key under ConfigMap data:
        if "kind: ConfigMap" not in original:
            continue
        fixed, n = re.subn(
            r"(kind: ConfigMap[\s\S]*?\ndata:\n(?:  \w+:.+\n)*)",
            r"\1  DATABASE_URL: postgres://payments:payments@db:5432/payments\n",
            original,
            count=1,
        )
        if n == 0:
            # Fallback: after APP_MODE / LOG_LEVEL line
            fixed, n = re.subn(
                r"(data:\n(?:  [A-Za-z0-9_]+:.+\n)*)",
                r"\1  DATABASE_URL: postgres://payments:payments@db:5432/payments\n",
                original,
                count=1,
            )
        if n == 0 or fixed == original:
            continue
        files.append(
            {
                "path": rel,
                "action": "modify",
                "content": fixed,
                "unified_diff_hunk": None,
            }
        )
    return files or None


def generate_files_for_diagnosis(run: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, str]:
    """Return (files, summary) for the selected failure class."""
    diagnosis = run.get("diagnosis") or {}
    failure_class = (diagnosis.get("classification") or {}).get("failure_class")
    if not failure_class:
        return None, "No deterministic fix template for failure class"

    from raphael_agent.learning import template_weight_for_run

    weight = template_weight_for_run(run, str(failure_class))
    if weight < 0.4:
        return (
            None,
            f"Learning demoted template for {failure_class} (weight={weight})",
        )

    # The patch-selector model chooses only from bounded template families.
    # Map its names to concrete generators; unknown families fall back to the
    # existing deterministic dispatcher and still require sandbox validation.
    model_template = str(run.get("_model_safe_template") or "")
    if model_template in {"fix_probe_port_mismatch", "adjust_readiness_probe_path", "tune_probe_timeout_seconds"}:
        files = fix_probe_port_mismatch(run)
        return files, "Apply model-selected readiness probe fix"
    if model_template in {"restore_known_good_image", "revert_image_digest"}:
        files = fix_bad_image(run)
        return files, "Apply model-selected known-good image fix"
    if model_template == "restore_configmap_key":
        files = fix_missing_configmap_key(run)
        return files, "Apply model-selected ConfigMap key fix"

    if failure_class == "probe_misconfiguration":
        files = fix_probe_port_mismatch(run)
        return files, "Align readiness probe port with containerPort"
    if failure_class == "bad_image_reference":
        files = fix_bad_image(run)
        return files, "Restore known-good container image tag"
    if failure_class == "invalid_missing_config":
        files = fix_missing_configmap_key(run)
        return files, "Add missing ConfigMap key referenced by the Deployment"
    return None, "No deterministic fix template for failure class"
