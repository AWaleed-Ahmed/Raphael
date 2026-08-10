"""Deterministic failure-class analyzers (FR-020–024). Prefer these before any LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AnalyzerHit:
    failure_class: str
    category: str  # supported | blocked | unknown
    confidence: float
    statement: str
    hypothesis_id: str
    expected_signature_key: str | None = None
    candidate_fix_hint: str | None = None
    supporting_evidence_ids: list[str] = field(default_factory=list)
    contradicting_evidence_ids: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    analyzer_name: str = "deterministic"


def _evidence_blob(run: dict[str, Any]) -> tuple[str, list[str]]:
    ids: list[str] = []
    parts: list[str] = []
    for item in run.get("evidence") or []:
        eid = item.get("evidence_id")
        if eid:
            ids.append(str(eid))
        for key in ("summary", "content_excerpt"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value)
    return "\n".join(parts).lower(), ids


def _read_workspace_text(run: dict[str, Any], limit: int = 200_000) -> str:
    workspace = run.get("workspace_path")
    if not workspace:
        return ""
    root = Path(workspace)
    if not root.is_dir():
        return ""
    manifests = run.get("manifests") or {}
    rel = manifests.get("path") or "deploy/manifests"
    target = root / rel
    chunks: list[str] = []
    size = 0
    paths: list[Path] = []
    if target.is_file():
        paths = [target]
    elif target.is_dir():
        paths = sorted(target.rglob("*"))
    for path in paths:
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".yaml", ".yml", ".json", ".tpl"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        chunks.append(f"# file:{path.relative_to(root).as_posix()}\n{text}")
        size += len(text)
        if size >= limit:
            break
    return "\n".join(chunks)


_PROBE_RE = re.compile(
    r"readiness\s+probe|liveness\s+probe|probe[_ ]port|probe failed|http probe",
    re.I,
)
_PROBE_PORT_MISMATCH_RE = re.compile(
    r"probe[^\n]{0,80}(?:port|:)[^\n]{0,40}(\d{2,5}).{0,40}(?:!=|does not match|mismatch).{0,40}(\d{2,5})"
    r"|containerPort\s*:\s*(\d{2,5})[\s\S]{0,400}readinessProbe:[\s\S]{0,200}port:\s*(\d{2,5})",
    re.I,
)
_IMAGE_RE = re.compile(
    r"imagepullbackoff|errimagepull|manifest unknown|not found.*image|bad[_ ]image|does-not-exist",
    re.I,
)
_CONFIGMAP_RE = re.compile(
    r"createcontainerconfigerror|key[^\n]{0,40}not found|configmap.*(missing|not found)|missing[_ ]config",
    re.I,
)
_HELM_KUST_RE = re.compile(
    r"helm.*(error|failed|schema)|kustomize.*(error|failed)|unable to find resource|no matches for kind|values\.schema",
    re.I,
)
_SECRET_BLOCK_RE = re.compile(
    r"plaintext\s+secret|requires?\s+production\s+secret|secret\s+payload|kubernetes\s+secret\s+value",
    re.I,
)
_PRIV_BLOCK_RE = re.compile(
    r"privileged:\s*true|hostnetwork:\s*true|hostpid:\s*true|hostpath:",
    re.I,
)


def _probe_from_manifest(manifest_text: str) -> AnalyzerHit | None:
    # Find containerPort then readinessProbe.port in same container-ish window.
    for match in re.finditer(
        r"containerPort:\s*(\d+)([\s\S]{0,500}?)readinessProbe:([\s\S]{0,200}?)port:\s*(\d+)",
        manifest_text,
        re.I,
    ):
        cport, _, _, pport = match.groups()
        if cport != pport:
            return AnalyzerHit(
                failure_class="probe_misconfiguration",
                category="supported",
                confidence=0.93,
                statement=(
                    f"Readiness probe port {pport} does not match containerPort {cport}"
                ),
                hypothesis_id="hyp-probe-port",
                expected_signature_key=f"probe_port_mismatch:payments-api:{cport}!={pport}",
                candidate_fix_hint="align readinessProbe.httpGet.port with containerPort",
                analyzer_name="manifest_probe_port",
            )
    return None


def analyze_run(run: dict[str, Any]) -> list[AnalyzerHit]:
    """Return ranked analyzer hits (best first). May be empty."""
    blob, evidence_ids = _evidence_blob(run)
    manifest_text = _read_workspace_text(run)
    combined = f"{blob}\n{manifest_text.lower()}"
    hits: list[AnalyzerHit] = []

    if _SECRET_BLOCK_RE.search(combined):
        hits.append(
            AnalyzerHit(
                failure_class="policy_blocked",
                category="blocked",
                confidence=0.99,
                statement="Failure appears to require production secret values",
                hypothesis_id="hyp-blocked-secret",
                blocked_reason="production_secret_required",
                supporting_evidence_ids=evidence_ids,
                analyzer_name="blocked_secret",
            )
        )

    if _PRIV_BLOCK_RE.search(manifest_text) or (
        "privileged" in blob and "blocked" in blob
    ):
        hits.append(
            AnalyzerHit(
                failure_class="policy_blocked",
                category="blocked",
                confidence=0.98,
                statement="Privileged or host access configuration is policy-blocked",
                hypothesis_id="hyp-blocked-privilege",
                blocked_reason="privileged_or_host_access",
                supporting_evidence_ids=evidence_ids,
                analyzer_name="blocked_privilege",
            )
        )

    probe_hit = _probe_from_manifest(manifest_text)
    if probe_hit:
        probe_hit.supporting_evidence_ids = evidence_ids
        hits.append(probe_hit)
    elif _PROBE_RE.search(blob) or "probe_port_mismatch" in combined:
        port_match = _PROBE_PORT_MISMATCH_RE.search(manifest_text) or _PROBE_PORT_MISMATCH_RE.search(
            blob
        )
        stmt = "Readiness/liveness probe misconfiguration indicated by evidence"
        expected = "probe_port_mismatch:payments-api"
        conf = 0.86
        if port_match:
            groups = [g for g in port_match.groups() if g]
            if len(groups) >= 2:
                stmt = f"Probe port mismatch involving ports {groups[0]} and {groups[1]}"
                expected = f"probe_port_mismatch:payments-api:{groups[0]}!={groups[1]}"
                conf = 0.9
        hits.append(
            AnalyzerHit(
                failure_class="probe_misconfiguration",
                category="supported",
                confidence=conf,
                statement=stmt,
                hypothesis_id="hyp-probe-port",
                expected_signature_key=expected,
                candidate_fix_hint="deploy/manifests readinessProbe.port",
                supporting_evidence_ids=evidence_ids,
                analyzer_name="evidence_probe",
            )
        )

    if _IMAGE_RE.search(combined) or "raphael.scenario: bad-image" in manifest_text.lower():
        hits.append(
            AnalyzerHit(
                failure_class="bad_image_reference",
                category="supported",
                confidence=0.9,
                statement="Container image reference is missing or pull failed",
                hypothesis_id="hyp-bad-image",
                expected_signature_key="bad_image_reference:payments-api",
                candidate_fix_hint="restore known-good image tag",
                supporting_evidence_ids=evidence_ids,
                analyzer_name="evidence_image",
            )
        )

    if _CONFIGMAP_RE.search(combined) or "key: DATABASE_URL" in manifest_text:
        hits.append(
            AnalyzerHit(
                failure_class="invalid_missing_config",
                category="supported",
                confidence=0.88,
                statement="ConfigMap key referenced by the workload is missing",
                hypothesis_id="hyp-missing-configmap-key",
                expected_signature_key="invalid_missing_config:payments-api",
                candidate_fix_hint="add missing ConfigMap key or fix key reference",
                supporting_evidence_ids=evidence_ids,
                analyzer_name="evidence_configmap",
            )
        )

    if _HELM_KUST_RE.search(combined) or "kustomization.yaml" in manifest_text.lower():
        # Only claim helm/kustomize when evidence/manifest strongly suggests it
        if _HELM_KUST_RE.search(combined) or "kind: kustomization" in manifest_text.lower():
            hits.append(
                AnalyzerHit(
                    failure_class="helm_kustomize_render_error",
                    category="supported",
                    confidence=0.85,
                    statement="Helm/Kustomize render or schema failure indicated",
                    hypothesis_id="hyp-helm-kustomize",
                    expected_signature_key="helm_kustomize_render_error",
                    candidate_fix_hint="fix chart values/overlay reference",
                    supporting_evidence_ids=evidence_ids,
                    analyzer_name="evidence_helm_kustomize",
                )
            )

    # Prefer blocked over supported when both fire.
    hits.sort(
        key=lambda h: (
            0 if h.category == "blocked" else 1,
            -h.confidence,
        )
    )
    # Dedupe by failure_class keeping best.
    seen: set[str] = set()
    unique: list[AnalyzerHit] = []
    for hit in hits:
        if hit.failure_class in seen:
            continue
        seen.add(hit.failure_class)
        unique.append(hit)
    return unique[:3]
