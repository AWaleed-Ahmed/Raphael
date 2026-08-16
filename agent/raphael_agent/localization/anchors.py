"""Runtime Release Resolver & Runtime Anchor Extractor (FLE / Steps 1-7).

Resolves runtime deployment identity from OCI labels and OTel resources, and extracts
source code/config anchors from exceptions, traces, logs, HTTP routes, and manifests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Standard framework and library path patterns to filter out of application stack traces
_FRAMEWORK_PATH_RE = re.compile(
    r"/site-packages/|/dist-packages/|/lib/python\d\.\d+/|/usr/lib/|"
    r"/starlette/|/fastapi/|/uvicorn/|/django/|/flask/|/werkzeug/|"
    r"/pytest/|/unittest/|/anyio/|/httpx/|/requests/|/node_modules/|"
    r"/vendor/|/internal/runtime/|/runtime/",
    re.I,
)


@dataclass
class DeploymentIdentity:
    """Step 1: Resolved deployment identity."""

    service_name: str
    environment: str
    git_sha: str
    repository: str
    image_digest: str | None = None
    build_id: str | None = None
    service_version: str | None = None
    source_map_reference: str | None = None
    sbom_reference: str | None = None

    def canonical_identity_string(self) -> str:
        digest = self.image_digest or "no_digest"
        return f"{self.service_name}:{self.environment}:{self.repository}@{self.git_sha} [{digest}]"


@dataclass
class RuntimeAnchor:
    """Step 2: Extracted runtime anchor connecting evidence to a source location."""

    signal_type: str  # exception | trace | log | http | probe | k8s_event | config | invariant
    file_path: str
    line_number: int
    symbol_name: str
    confidence: float
    evidence_ref: str
    raw_details: dict[str, Any] = field(default_factory=dict)


def resolve_deployment_identity(payload_or_labels: dict[str, Any]) -> DeploymentIdentity:
    """Extract and resolve exact deployment release from OCI labels and OTel resources."""
    labels = payload_or_labels.get("labels") or payload_or_labels.get("attributes") or payload_or_labels

    # 1. Repository
    repo = (
        labels.get("org.opencontainers.image.source")
        or labels.get("repository")
        or labels.get("repo")
        or "raphael/workload"
    )

    # 2. Git SHA / Revision
    git_sha = (
        labels.get("org.opencontainers.image.revision")
        or labels.get("git_sha")
        or labels.get("commit_sha")
        or labels.get("service.version")
        or "0000000"
    )

    # 3. Image Digest
    digest = (
        labels.get("container.image.id")
        or labels.get("image_digest")
        or labels.get("image_id")
    )

    # 4. Service & Environment
    service = (
        labels.get("service.name")
        or labels.get("service")
        or labels.get("app")
        or labels.get("k8s.deployment.name")
        or "workload"
    )
    env = (
        labels.get("deployment.environment.name")
        or labels.get("environment")
        or labels.get("env")
        or "staging"
    )

    return DeploymentIdentity(
        service_name=str(service),
        environment=str(env),
        git_sha=str(git_sha)[:40],
        repository=str(repo),
        image_digest=str(digest) if digest else None,
        service_version=str(labels.get("org.opencontainers.image.version") or labels.get("service.version") or ""),
    )


def extract_stack_trace_anchors(stack_trace_text: str, evidence_ref: str = "ev-stack-01") -> list[RuntimeAnchor]:
    """Step 3: Parse stack trace, remove framework frames, and extract top application anchors."""
    if not stack_trace_text:
        return []

    lines = stack_trace_text.splitlines()
    raw_frames: list[tuple[str, int, str]] = []

    for line in lines:
        m = re.search(r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+(\w+)', line)
        if m:
            path, lineno, func = m.group(1), int(m.group(2)), m.group(3)
            raw_frames.append((path, lineno, func))

    # Filter out framework frames
    app_frames = [f for f in raw_frames if not _FRAMEWORK_PATH_RE.search(f[0])]
    if not app_frames and raw_frames:
        # If all were framework frames, fallback to raw frames
        app_frames = raw_frames

    anchors: list[RuntimeAnchor] = []
    # Invert to prioritize deepest application frame first
    for rank, (path, lineno, func) in enumerate(reversed(app_frames[:5])):
        # Deepest frame gets highest confidence (1.0 -> 0.8 -> 0.6)
        conf = max(0.4, 1.0 - (rank * 0.15))
        clean_path = path.lstrip("/")
        anchors.append(
            RuntimeAnchor(
                signal_type="exception",
                file_path=clean_path,
                line_number=lineno,
                symbol_name=func,
                confidence=conf,
                evidence_ref=evidence_ref,
                raw_details={"rank": rank + 1, "is_deepest": rank == 0},
            )
        )

    return anchors


def extract_trace_divergence_anchor(
    current_spans: list[dict[str, Any]],
    golden_span_names: list[str],
    evidence_ref: str = "ev-trace-01",
) -> RuntimeAnchor | None:
    """Step 4: Diff failing trace against golden trace to find the FIRST divergent or erroneous span."""
    if not current_spans:
        return None

    # Check for first span that deviates from golden trace or has error status
    first_divergent_span: dict[str, Any] | None = None

    for idx, span in enumerate(current_spans):
        attrs = span.get("attributes") or span
        span_name = str(attrs.get("name") or attrs.get("operation_name") or attrs.get("resource") or "")
        is_error = bool(attrs.get("error") or attrs.get("error.type") or str(attrs.get("status_code", "")).startswith("5"))

        # Case A: Span marked as error
        if is_error:
            first_divergent_span = span
            break

        # Case B: Span deviated from golden sequence
        if golden_span_names and idx < len(golden_span_names):
            expected_name = golden_span_names[idx]
            if span_name and expected_name and span_name != expected_name:
                first_divergent_span = span
                break

    # If no explicit divergence found, pick first span with highest latency or first span
    if not first_divergent_span and current_spans:
        first_divergent_span = current_spans[0]

    attrs = first_divergent_span.get("attributes") or first_divergent_span
    file_path = str(attrs.get("code.file.path") or attrs.get("code.filepath") or "src/service.py")
    line_no = int(attrs.get("code.line.number") or attrs.get("code.lineno") or 1)
    func_name = str(attrs.get("code.function.name") or attrs.get("name") or attrs.get("resource") or "main")

    return RuntimeAnchor(
        signal_type="trace",
        file_path=file_path.lstrip("/"),
        line_number=line_no,
        symbol_name=func_name,
        confidence=0.90,
        evidence_ref=evidence_ref,
        raw_details={"span_name": func_name, "operation": attrs.get("operation_name")},
    )


def extract_route_to_handler_anchor(
    http_route: str,
    route_catalog_map: dict[str, dict[str, Any]],
    evidence_ref: str = "ev-route-01",
) -> RuntimeAnchor | None:
    """Step 6: Map HTTP route template to registered handler function in catalog."""
    clean_route = http_route.strip()
    match_entry = route_catalog_map.get(clean_route)
    if not match_entry:
        # Try finding template match e.g. /orders/123 matches /orders/{id}
        for template, entry in route_catalog_map.items():
            pattern = re.sub(r"\{[a-zA-Z0-9_]+\}", r"[^/]+", template)
            if re.match(f"^{pattern}$", clean_route):
                match_entry = entry
                break

    if not match_entry:
        return None

    return RuntimeAnchor(
        signal_type="http",
        file_path=str(match_entry.get("path") or "src/routes.py"),
        line_number=int(match_entry.get("line") or 1),
        symbol_name=str(match_entry.get("symbol") or "handler"),
        confidence=0.85,
        evidence_ref=evidence_ref,
        raw_details={"route": clean_route},
    )


def extract_kubernetes_manifest_anchors(
    k8s_evidence: dict[str, Any],
    evidence_ref: str = "ev-k8s-01",
) -> list[RuntimeAnchor]:
    """Step 7: Map Kubernetes probe / container / config error back to manifest fields."""
    anchors: list[RuntimeAnchor] = []
    reason = str(k8s_evidence.get("reason") or k8s_evidence.get("k8s_event_reason") or "")
    manifest_path = str(k8s_evidence.get("manifest_path") or "deploy/manifests/deployment.yaml")
    
    if "probe" in reason.lower():
        anchors.append(
            RuntimeAnchor(
                signal_type="probe",
                file_path=manifest_path,
                line_number=k8s_evidence.get("line_number", 42),
                symbol_name="readinessProbe.httpGet.port",
                confidence=0.95,
                evidence_ref=evidence_ref,
                raw_details={"reason": reason},
            )
        )
    elif "image" in reason.lower() or "imagepullbackoff" in reason.lower():
        anchors.append(
            RuntimeAnchor(
                signal_type="config",
                file_path=manifest_path,
                line_number=k8s_evidence.get("line_number", 18),
                symbol_name="spec.template.spec.containers[0].image",
                confidence=0.95,
                evidence_ref=evidence_ref,
                raw_details={"reason": reason},
            )
        )
    elif "configmap" in reason.lower() or "createcontainerconfigerror" in reason.lower():
        anchors.append(
            RuntimeAnchor(
                signal_type="config",
                file_path=manifest_path,
                line_number=k8s_evidence.get("line_number", 30),
                symbol_name="envFrom.configMapRef",
                confidence=0.95,
                evidence_ref=evidence_ref,
                raw_details={"reason": reason},
            )
        )

    return anchors
