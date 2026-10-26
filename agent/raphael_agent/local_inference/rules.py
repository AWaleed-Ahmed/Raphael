"""Deterministic, vendor-neutral evidence rules used before ML inference."""

from __future__ import annotations

from typing import Any

REASON_RULES = {
    "ImagePullBackOff": "bad_image_reference",
    "ErrImagePull": "bad_image_reference",
    "ImagePullAuthFailure": "bad_image_reference",
    "ImageTagNotFound": "bad_image_reference",
    "InvalidImageName": "bad_image_reference",
    "RegistryManifestUnknown": "bad_image_reference",
    "OOMKilled": "resource_exhaustion",
    "ContainerMemoryQuotaExceeded": "resource_exhaustion",
    "CPUThrottlingStarvation": "resource_exhaustion",
    "EphemeralStoragePressure": "resource_exhaustion",
    "FileDescriptorExhaustion": "resource_exhaustion",
    "ThreadLimitExceeded": "resource_exhaustion",
    "CreateContainerConfigError": "invalid_missing_config",
    "EnvVarParseError": "invalid_missing_config",
    "InvalidConfigSchema": "invalid_missing_config",
    "MissingConfigMapKeyRef": "invalid_missing_config",
    "MissingSecretKeyRef": "invalid_missing_config",
    "UnresolvedEnvSubstitution": "invalid_missing_config",
    "LivenessProbeHTTP404": "probe_misconfiguration",
    "LivenessProbeThresholdExceeded": "probe_misconfiguration",
    "ProbeInitialDelayTooShort": "probe_misconfiguration",
    "ReadinessProbePathInvalid": "probe_misconfiguration",
    "ReadinessProbePortMismatch": "probe_misconfiguration",
    "StartupProbeTimeout": "probe_misconfiguration",
    "ConnectionRefusedOnPort": "service_port_mismatch",
    "EndpointResolutionFailed": "service_port_mismatch",
    "IngressBackendPortNotFound": "service_port_mismatch",
    "NamedPortUnresolved": "service_port_mismatch",
    "NoEndpointsAvailable": "service_port_mismatch",
    "ServiceTargetPortMismatch": "service_port_mismatch",
    "UnauthorizedUpstreamAccess": "auth_denied",
    "RBACPermissionDenied": "auth_denied",
    "OAuthScopeMissing": "auth_denied",
    "JWTValidationFailed": "auth_denied",
    "ServiceAccountTokenExpired": "auth_denied",
    "HTTPClientTimeout": "dependency_timeout",
    "GRPCStatusDeadlineExceeded": "dependency_timeout",
    "DownstreamDeadlineExceeded": "dependency_timeout",
    "UpstreamGatewayTimeout": "dependency_timeout",
    "SocketReadTimeout": "dependency_timeout",
    "ConnectionRefusedByDatabase": "db_error",
    "DatabaseDeadlockDetected": "db_error",
    "DatabasePoolExhausted": "db_error",
    "MigrationColumnMissing": "db_error",
    "SQLQueryExecutionError": "db_error",
    "TransactionTimeoutExceeded": "db_error",
    "DNSResolutionFailed": "network_error",
    "TCPConnectionRefused": "network_error",
    "ConnectionResetByPeer": "network_error",
    "MTLSHandshakeFailed": "network_error",
    "NetworkPolicyBlockedEgress": "network_error",
    "NoRouteToHost": "network_error",
    "AlgorithmicComplexitySpike": "latency_regression",
    "LockContentionBottleneck": "latency_regression",
    "NPlusOneQueryRegression": "latency_regression",
    "P99LatencyThresholdBreached": "latency_regression",
    "SlowResponseP95Exceeded": "latency_regression",
    "SerializationThroughputDegradation": "latency_regression",
    "ContextPropagationDropped": "trace_divergence",
    "CyclicSpanInvocation": "trace_divergence",
    "MissingTelemetrySpanSequence": "trace_divergence",
    "RouteDivergenceBypass": "trace_divergence",
    "SpanSequenceAnomaly": "trace_divergence",
    "UnexpectedSubserviceInvocation": "trace_divergence",
}
PREFIX_RULES = {
    "image_pull_backoff": "bad_image_reference",
    "err_image_pull": "bad_image_reference",
    "image_auth_failed": "bad_image_reference",
    "image_tag_not_found": "bad_image_reference",
    "registry_manifest_unknown": "bad_image_reference",
    "oom_killed_exit_137": "resource_exhaustion",
    "cgroup_memory_limit": "resource_exhaustion",
    "cpu_cfs_throttled": "resource_exhaustion",
    "ephemeral_storage_eviction": "resource_exhaustion",
    "fd_leak_limit": "resource_exhaustion",
    "container_config_error": "invalid_missing_config",
    "config_schema_invalid": "invalid_missing_config",
    "env_parse_int_error": "invalid_missing_config",
    "missing_configmap_key": "invalid_missing_config",
    "secret_key_ref_missing": "invalid_missing_config",
    "readiness_probe_failing": "probe_misconfiguration",
    "probe_404_path": "probe_misconfiguration",
    "probe_port_mismatch": "probe_misconfiguration",
    "liveness_probe_crash": "probe_misconfiguration",
    "startup_probe_timeout": "probe_misconfiguration",
    "target_port_mismatch": "service_port_mismatch",
    "service_conn_refused": "service_port_mismatch",
    "container_port_divergence": "service_port_mismatch",
    "no_endpoints_for_service": "service_port_mismatch",
    "ingress_port_unreachable": "service_port_mismatch",
}


def evidence_text(record: dict[str, Any]) -> str:
    keys = (
        "fingerprint",
        "normalized_reason",
        "message",
        "summary",
        "reason",
        "event_reason",
        "evidence_text",
    )
    return " ".join(str(record.get(key) or "") for key in keys).lower()


def deterministic_failure_class(
    record: dict[str, Any],
) -> tuple[str | None, str | None]:
    reason = str(record.get("normalized_reason") or "")
    if reason in REASON_RULES:
        return REASON_RULES[reason], f"normalized_reason:{reason}"
    prefix = str(record.get("fingerprint") or "").split(":", 1)[0].lower()
    if prefix in PREFIX_RULES:
        return PREFIX_RULES[prefix], f"fingerprint_prefix:{prefix}"
    text = evidence_text(record)
    phrases = (
        (("imagepullbackoff", "errimagepull", "image pull"), "bad_image_reference"),
        (("oomkilled", "out of memory", "exit 137"), "resource_exhaustion"),
        (
            ("createcontainerconfigerror", "missing configmap", "missing secret key"),
            "invalid_missing_config",
        ),
        (
            ("readiness probe", "liveness probe", "startup probe"),
            "probe_misconfiguration",
        ),
        (("targetport", "target port", "no endpoints"), "service_port_mismatch"),
        (
            ("deadline exceeded", "gateway timeout", "client timeout"),
            "dependency_timeout",
        ),
        (("rbac", "unauthorized", "oauth scope", "jwt validation"), "auth_denied"),
        (("deadlock", "sql error", "database pool", "migration column"), "db_error"),
        (("dns resolution", "connection reset", "mtls handshake"), "network_error"),
    )
    for needles, label in phrases:
        if any(needle in text for needle in needles):
            return label, f"evidence_phrase:{label}"
    return None, None


def candidate_evidence_score(row: dict[str, Any]) -> float:
    """Apply the same deterministic ranking equation as the agent FLE."""
    stack = float(
        row.get("stack_trace_match") or row.get("runtime_anchor_score") or 0.0
    )
    changed = float(
        row.get("changed_line_overlap") or row.get("changed_file_match") or 0.0
    )
    trace = float(
        row.get("first_divergent_span") or row.get("trace_divergence_match") or 0.0
    )
    logs = float(
        row.get("log_correlation_score") or row.get("log_callsite_match") or 0.0
    )
    distance = max(0.0, float(row.get("dependency_distance") or 0.0))
    dependency = float(row.get("dependency_path_relevance") or (1.0 / (1.0 + distance)))
    return min(
        1.0,
        max(
            0.0,
            (0.30 * stack)
            + (0.25 * changed)
            + (0.20 * trace)
            + (0.15 * logs)
            + (0.10 * dependency),
        ),
    )


def rule_patch_template(record: dict[str, Any]) -> tuple[str | None, str | None]:
    failure_class, evidence = deterministic_failure_class(record)
    if failure_class is None:
        failure_class = str(record.get("failure_class") or "")
    reason = str(record.get("normalized_reason") or "")
    text = evidence_text(record)
    field = str(record.get("manifest_field") or "").lower()
    if str(record.get("candidate_type") or "") not in {
        "kubernetes_manifest",
        "configuration",
        "source_code",
    }:
        return None, "unsupported_candidate_type"
    if failure_class == "bad_image_reference":
        return (
            "restore_known_good_image",
            evidence or "failure_class:bad_image_reference",
        )
    if failure_class == "resource_exhaustion":
        if reason == "OOMKilled" or "memory" in field or "oom" in text:
            return "increase_memory_limit", evidence or "memory_limit_evidence"
        return (
            "patch_resource_exhaustion_logic",
            evidence or "resource_exhaustion_evidence",
        )
    if failure_class == "invalid_missing_config":
        if "secret" in text and "configmap" not in text:
            return (
                "patch_invalid_missing_config_logic",
                evidence or "secret_config_evidence",
            )
        return "restore_configmap_key", evidence or "configmap_evidence"
    if failure_class == "service_port_mismatch":
        return "fix_service_target_port", evidence or "target_port_evidence"
    if failure_class == "probe_misconfiguration":
        if "port" in text or "targetport" in field:
            return "fix_probe_port_mismatch", evidence or "probe_port_evidence"
        if "404" in text or "path" in text:
            return "adjust_readiness_probe_path", evidence or "probe_path_evidence"
        if "timeout" in text or "deadline" in text:
            return "tune_probe_timeout_seconds", evidence or "probe_timeout_evidence"
    return None, "insufficient_remediation_evidence"
