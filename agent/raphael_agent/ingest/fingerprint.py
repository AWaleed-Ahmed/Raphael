"""3-Layer Failure Fingerprinting Engine (FR-003 / Deduplication & Causality).

Layers:
1. Event Fingerprint: Deduplicates repeated webhooks from monitoring providers (Alertmanager groupKey, Datadog monitor ID, CloudWatch alarm ARN).
2. Canonical Incident Fingerprint: Provider-agnostic grouping of multi-provider signals (Prometheus + Datadog + CloudWatch) for the same outage.
   Format: v1|tenant|service|environment|release|symptom_class|operation|error_class|cause_anchor
3. Causal Fingerprint: Immutable signature that must reproduce in the sandbox before patching and disappear after patching.
   Format: failure-class:code-or-config-anchor:normalized-error:behavior-signature
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

# Regex patterns for strict exclusion filters
_TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b|"
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\b|"
    r"\b17\d{8,10}(?:\.\d+)?\b"  # Unix epoch timestamps
)
_POD_SUFFIX_RE = re.compile(r"-(?=[a-z0-9]*\d)[a-z0-9]{7,10}-(?=[a-z0-9]*\d)[a-z0-9]{4,6}\b|-(?=[0-9a-f]*\d)[0-9a-f]{7,12}\b")
_MEM_ADDR_RE = re.compile(r"\b0x[0-9a-fA-F]{6,16}\b")
_UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_REQ_ID_RE = re.compile(r"\b(?:req|request|trace|span|corr|session)[-_][a-zA-Z0-9_-]{8,36}\b", re.I)
_HEX_RE = re.compile(r"\b[0-9a-f]{12,64}\b", re.I)


def _clean_component(value: Any, default: str) -> str:
    """Normalize one fingerprint component consistently across all layers."""
    cleaned = sanitize_fingerprint_text(str(value or default)).lower()
    return cleaned or default


def sanitize_fingerprint_text(text: str) -> str:
    """Strip unstable noise (timestamps, pod UUIDs, memory addresses, request IDs) from input."""
    if not text:
        return ""
    s = text.strip()
    s = _TIMESTAMP_RE.sub("<TIME>", s)
    s = _UUID_RE.sub("<UUID>", s)
    s = _REQ_ID_RE.sub("<REQ_ID>", s)
    s = _MEM_ADDR_RE.sub("<MEM_ADDR>", s)
    s = _POD_SUFFIX_RE.sub("<POD_SUFFIX>", s)
    # Collapse multiple whitespace / punctuation
    s = re.sub(r"[\s\t\n]+", " ", s)
    return s.strip()

def normalize_symptom_class(value: str) -> str:
    """Map provider-specific alert names into stable incident symptom classes."""
    text = sanitize_fingerprint_text(value).lower()
    compact = re.sub(r"[^a-z0-9]+", " ", text)
    if re.search(r"5xx|http error|error rate|target.*5xx|server error", compact):
        return "http_error"
    if re.search(r"latency|p99|p95|response time|slow", compact):
        return "latency_regression"
    if re.search(r"oom|out of memory|memory pressure|cpu thrott|resource", compact):
        return "resource_exhaustion"
    if re.search(r"probe|unhealthy|availability|service down|not ready", compact):
        return "availability_failure"
    if re.search(r"imagepull|image pull|deployment|rollout|container", compact):
        return "deployment_failure"
    if re.search(r"timeout|connection refused|dns|tls|network", compact):
        return "dependency_failure"
    if re.search(r"queue|backlog|dead letter|dlq", compact):
        return "queue_backlog"
    if re.search(r"permission|forbidden|access denied|unauthorized", compact):
        return "auth_denied"
    if re.search(r"config|missing|invalid", compact):
        return "configuration_failure"
    return _clean_component(text, "generic_failure")


def normalize_stack_trace_frames(frames_or_text: list[str] | str, max_frames: int = 3) -> str:
    """Extract and normalize the top N most relevant application stack frames."""
    if isinstance(frames_or_text, str):
        lines = [line.strip() for line in frames_or_text.splitlines() if line.strip()]
        # Extract lines resembling File "...", line X, in Y
        frame_matches = []
        for line in lines:
            m = re.search(r'File "([^"]+)", line (\d+), in (\w+)', line)
            if m:
                path, lineno, func = m.group(1), m.group(2), m.group(3)
                filename = path.split("/")[-1]
                frame_matches.append(f"{filename}:{lineno}:{func}")
        if frame_matches:
            return "|".join(frame_matches[:max_frames])
        # Fallback: sanitized first few lines
        sanitized = sanitize_fingerprint_text("\n".join(lines[:max_frames]))
        return sanitized[:120]

    # If list of frame strings
    clean_frames = []
    for f in frames_or_text[:max_frames]:
        clean_frames.append(sanitize_fingerprint_text(str(f)))
    return "|".join(clean_frames) if clean_frames else "no_stack"


def normalize_exception_type(value: Any) -> str:
    """Normalize framework-qualified exception names to a stable leaf type."""
    text = sanitize_fingerprint_text(str(value or "Exception"))
    return text.rsplit(".", 1)[-1].lower() or "exception"


def normalize_http_body_pattern(value: Any) -> str:
    """Keep an HTTP body shape while removing IDs, URLs, timestamps, and values."""
    text = sanitize_fingerprint_text(str(value or ""))
    if not text:
        return "no_body"
    text = _HEX_RE.sub("<HEX>", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\b", "<N>", text)
    text = re.sub(r"https?://\S+", "<URL>", text, flags=re.I)
    text = re.sub(r"(:\s*)([\"'])(?:[^\"']{1,80})(\2)", r"\1<VALUE>", text)
    text = re.sub(r"(=\s*)([^,}\s]+)", r"\1<VALUE>", text)
    return text[:240].lower()


def normalize_log_window(value: Any, *, max_lines: int = 6) -> str:
    """Normalize the bounded log window around the first error."""
    lines = str(value or "").splitlines()
    cleaned = [sanitize_fingerprint_text(line) for line in lines if line.strip()]
    return "|".join(cleaned[:max_lines])[:600].lower() or "no_logs"


def runtime_fingerprint_components(seed: dict[str, Any]) -> dict[str, str]:
    """Extract stable runtime dimensions used by incident/causal fingerprints."""
    observation = dict(seed.get("runtime_observation") or {})
    signature = seed.get("failure_signature") or {}
    normalized = signature.get("normalized") if isinstance(signature, dict) else {}
    if isinstance(normalized, dict):
        observation = {**normalized, **observation}
        attrs = normalized.get("attributes")
        if isinstance(attrs, dict):
            observation = {**attrs, **observation}
    stack = observation.get("stack_trace") or observation.get("exception.stacktrace") or observation.get("normalized_stack_trace")
    spans = observation.get("span_sequence") or observation.get("spans") or []
    first_span = observation.get("first_unhealthy_span") or observation.get("first_divergent_span")
    if not first_span and isinstance(spans, list):
        for span in spans:
            attrs = span.get("attributes") or span if isinstance(span, dict) else span
            attrs = attrs if isinstance(attrs, dict) else {}
            if attrs.get("error") or attrs.get("error.type") or str(attrs.get("status_code") or "").startswith("5"):
                first_span = attrs.get("name") or attrs.get("operation_name") or attrs.get("resource")
                break
    status = observation.get("status_code") or observation.get("http.status_code") or observation.get("http_status")
    body = observation.get("http_body") or observation.get("response_body") or observation.get("body_pattern")
    return {
        "exit": str(observation.get("exit_code") or observation.get("container_exit_code") or "none").lower(),
        "signal": str(observation.get("signal") or observation.get("termination_signal") or "none").lower(),
        "exception": normalize_exception_type(observation.get("exception_type") or observation.get("error.type") or "Exception"),
        "stack": normalize_stack_trace_frames(stack or "", max_frames=5),
        "probe": _clean_component(observation.get("probe_reason") or observation.get("k8s_event_reason") or observation.get("reason"), "none"),
        "span": _clean_component(first_span, "none"),
        "http": f"{str(status or 'none').lower()}:{normalize_http_body_pattern(body)}",
        "logs": normalize_log_window(observation.get("log_window") or observation.get("logs") or observation.get("log_excerpt")),
        "invariant": _clean_component(observation.get("invariant") or observation.get("invariant_name") or observation.get("slo") or observation.get("synthetic_check"), "none"),
    }


def build_runtime_fingerprint(seed: dict[str, Any]) -> str:
    """Build a stable runtime fingerprint for deduplication and causality."""
    parts = runtime_fingerprint_components(seed)
    raw = "v2|" + "|".join(f"{key}={parts[key]}" for key in sorted(parts))
    return f"{raw}|sha256={hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


@dataclass
class EventFingerprint:
    """Layer 1: Webhook delivery deduplication key."""

    provider: str
    event_type: str
    provider_event_id: str
    raw_key: str

    @classmethod
    def create(cls, provider: str, event_type: str, provider_event_id: str) -> EventFingerprint:
        prov = _clean_component(provider, "generic")
        etype = _clean_component(event_type, "alert")
        peid = _clean_component(provider_event_id, "event")
        key = f"{prov}:{etype}:{peid}"
        return cls(provider=prov, event_type=etype, provider_event_id=peid, raw_key=key)


@dataclass
class IncidentFingerprint:
    """Layer 2: Canonical Cross-Provider Incident Grouping Key."""

    canonical_string: str
    sha256_hash: str
    tenant: str
    service: str
    environment: str
    release: str
    symptom_class: str
    operation: str
    error_class: str
    cause_anchor: str

    @classmethod
    def create(
        cls,
        *,
        tenant: str = "default",
        service: str = "workload",
        environment: str = "staging",
        release: str = "HEAD",
        symptom_class: str = "generic_failure",
        operation: str = "main",
        error_class: str = "error",
        cause_anchor: str = "",
    ) -> IncidentFingerprint:
        clean_tenant = _clean_component(tenant, "default")
        clean_service = _clean_component(service, "workload")
        clean_env = _clean_component(environment, "staging")
        clean_release = _clean_component(release, "HEAD")[:12]
        clean_symptom = _clean_component(symptom_class, "failure")
        clean_operation = _clean_component(operation, "main")
        clean_error = _clean_component(error_class, "error")
        clean_anchor = sanitize_fingerprint_text(str(cause_anchor or "")).lower()

        # Format: v1|tenant|service|environment|release|symptom_class|operation|error_class|cause_anchor
        canonical = (
            f"v1|{clean_tenant}|{clean_service}|{clean_env}|{clean_release}|"
            f"{clean_symptom}|{clean_operation}|{clean_error}|{clean_anchor}"
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

        return cls(
            canonical_string=canonical,
            sha256_hash=digest,
            tenant=clean_tenant,
            service=clean_service,
            environment=clean_env,
            release=clean_release,
            symptom_class=clean_symptom,
            operation=clean_operation,
            error_class=clean_error,
            cause_anchor=clean_anchor,
        )


@dataclass
class CausalFingerprint:
    """Layer 3: Sandbox Verification Signature."""

    failure_class: str
    code_or_config_anchor: str
    normalized_error: str
    behavior_signature: str
    raw_key: str
    sha256_hash: str

    @classmethod
    def create(
        cls,
        failure_class: str,
        code_or_config_anchor: str,
        normalized_error: str,
        behavior_signature: str = "",
    ) -> CausalFingerprint:
        fclass = _clean_component(failure_class, "unknown")
        anchor = _clean_component(code_or_config_anchor, "unknown")
        nerror = _clean_component(normalized_error, "error")
        bsig = _clean_component(behavior_signature, "crash")

        raw_key = f"{fclass}:{anchor}:{nerror}:{bsig}"
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]

        return cls(
            failure_class=fclass,
            code_or_config_anchor=anchor,
            normalized_error=nerror,
            behavior_signature=bsig,
            raw_key=raw_key,
            sha256_hash=digest,
        )


def build_event_fingerprint(
    provider: str,
    event_type: str,
    provider_event_id: str,
) -> str:
    """Build a Layer 1 event deduplication key."""
    return EventFingerprint.create(provider, event_type, provider_event_id).raw_key


def build_canonical_incident_fingerprint(
    *,
    tenant: str = "default",
    service: str = "workload",
    environment: str = "staging",
    release: str = "HEAD",
    symptom_class: str = "failure",
    operation: str = "main",
    error_class: str = "error",
    cause_anchor: str = "",
) -> IncidentFingerprint:
    """Build a Layer 2 canonical incident key (groups Prometheus, Datadog, AWS for the same bug)."""
    return IncidentFingerprint.create(
        tenant=tenant,
        service=service,
        environment=environment,
        release=release,
        symptom_class=symptom_class,
        operation=operation,
        error_class=error_class,
        cause_anchor=cause_anchor,
    )


def build_causal_fingerprint(
    failure_class: str,
    code_or_config_anchor: str,
    normalized_error: str,
    behavior_signature: str = "",
) -> str:
    """Build a Layer 3 causal key for sandbox reproduction and verification."""
    return CausalFingerprint.create(
        failure_class=failure_class,
        code_or_config_anchor=code_or_config_anchor,
        normalized_error=normalized_error,
        behavior_signature=behavior_signature,
    ).raw_key


def provisional_failure_key(seed: dict[str, Any]) -> str:
    """Build a provisional failure key (Layer 2) from seed correlation fields."""
    correlation = seed.get("correlation") or {}
    if correlation.get("provisional_failure_key"):
        return str(correlation["provisional_failure_key"])

    trigger_kind = str(seed.get("trigger", {}).get("kind") or "generic")
    service = str(correlation.get("workload") or "workload")
    symptom = str(correlation.get("workflow_name") or correlation.get("check_name") or trigger_kind)
    return f"{service}|{symptom}"


def build_fingerprint(seed: dict[str, Any]) -> str:
    """Build canonical deduplication key for run_record."""
    repo = seed.get("repository") or {}
    owner = repo.get("owner", "")
    name = repo.get("name", "")
    service = str((seed.get("correlation") or {}).get("workload") or name or "workload")
    env = str(seed.get("target_environment") or "default")
    tenant = str(seed.get("tenant_id") or "local-dev")
    commit = str(seed.get("commit_sha") or "HEAD")[:12]

    correlation = seed.get("correlation") or {}
    existing = str(correlation.get("provisional_failure_key") or "")
    # APM normalizers already compute the canonical Layer 2 key.
    if existing.startswith("v1|"):
        return existing
    symptom = str(correlation.get("workflow_name") or correlation.get("check_name") or "failure")
    operation = str(correlation.get("deployment_config_path") or correlation.get("namespace") or "deploy")
    error_class = str(correlation.get("provisional_failure_key") or "error")

    runtime = runtime_fingerprint_components(seed)
    runtime_anchor = "|".join(
        f"{key}={runtime[key]}"
        for key in ("exception", "stack", "probe", "span", "http", "invariant")
        if runtime[key] not in {"none", "no_stack", "none:no_body"}
    )
    cause_anchor = f"{owner}/{name}"
    if runtime_anchor:
        cause_anchor = f"{cause_anchor}|{runtime_anchor}"
    inc = build_canonical_incident_fingerprint(
        tenant=tenant,
        service=service,
        environment=env,
        release=commit,
        symptom_class=symptom,
        operation=operation,
        error_class=error_class,
        cause_anchor=cause_anchor,
    )
    return inc.canonical_string
