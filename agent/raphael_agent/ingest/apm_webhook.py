"""APM, Prometheus Alertmanager, Datadog, and AWS CloudWatch webhook normalizer for Raphael (FR-001 / Ingest)."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from raphael_agent.ingest.fingerprint import (
    build_canonical_incident_fingerprint,
    build_event_fingerprint,
    build_fingerprint,
    normalize_symptom_class,
)
from raphael_agent.timeutil import utc_now


def _tenant_id(explicit: str | None = None) -> str:
    return explicit or os.environ.get("RAPHAEL_AGENT_TENANT_ID", "local-dev")


def normalize_alertmanager_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Prometheus Alertmanager webhook payload into a Raphael run seed with 3-layer fingerprints."""
    alerts = payload.get("alerts") or []
    first_alert = alerts[0] if alerts else {}
    labels = first_alert.get("labels") or {}
    annotations = first_alert.get("annotations") or {}

    alertname = str(labels.get("alertname") or "ApmPerformanceAlert")
    workload = str(labels.get("service") or labels.get("job") or labels.get("app") or "workload")
    namespace = str(labels.get("namespace") or "default")
    severity = str(labels.get("severity") or "critical")
    environment = str(labels.get("environment") or "staging")

    repo_owner = str(labels.get("repo_owner") or os.environ.get("RAPHAEL_DEFAULT_REPO_OWNER", "raphael"))
    repo_name = str(labels.get("repo_name") or os.environ.get("RAPHAEL_DEFAULT_REPO_NAME", workload))
    commit_sha = str(
        labels.get("commit_sha")
        or annotations.get("commit_sha")
        or "0000000"
    )
    if len(commit_sha) < 7:
        commit_sha = "0000000"

    summary = str(annotations.get("summary") or annotations.get("description") or f"Alert: {alertname} on {workload}")

    # 1. Event Fingerprint
    native_fp = first_alert.get("fingerprint")
    group_key = payload.get("groupKey") or f"{namespace}/{workload}/{alertname}"
    occurrence = str(first_alert.get("startsAt") or first_alert.get("endsAt") or "")
    event_id = build_event_fingerprint("alertmanager", "alert", f"{native_fp or group_key}:{occurrence}")
    run_id = f"run-{uuid.uuid4().hex[:12]}"

    # 2. Canonical Incident Fingerprint
    inc_fp = build_canonical_incident_fingerprint(
        tenant=_tenant_id(),
        service=workload,
        environment=environment,
        release=commit_sha,
        symptom_class=normalize_symptom_class(f"{alertname} {summary}"),
        operation=namespace,
        error_class=normalize_symptom_class(f"{alertname} {summary}"),
        cause_anchor=f"{repo_owner}/{repo_name}",
    )

    resources = [
        {
            "kind": labels.get("workload_kind") or "Deployment",
            "name": workload,
            "namespace": namespace,
        }
    ]

    seed: dict[str, Any] = {
        "run_id": run_id,
        "tenant_id": _tenant_id(),
        "trigger": {
            "kind": "alertmanager",
            "event_id": event_id,
            "received_at": utc_now(),
            "raw_ref": f"alertmanager:{alertname}",
        },
        "repository": {
            "owner": repo_owner,
            "name": repo_name,
        },
        "commit_sha": commit_sha,
        "target_environment": environment,
        "failure_fingerprint": inc_fp.canonical_string,

        "affected_resources": resources,
        "correlation": {
            "workload": workload,
            "namespace": namespace,
            "workflow_name": alertname,
            "check_name": severity,
            "provisional_failure_key": inc_fp.canonical_string,
        },
        "notes": summary,
        "runtime_observation": {
            "reason": summary,
            "slo": alertname,
            "http_status": labels.get("status_code") or labels.get("http.status_code"),
            "log_window": annotations.get("log_window") or annotations.get("logs"),
        },
    }
    seed["failure_fingerprint"] = build_fingerprint(seed)
    return seed


def normalize_datadog_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Datadog monitor webhook payload into a Raphael run seed with 3-layer fingerprints."""
    title = str(payload.get("title") or payload.get("event_title") or "Datadog Monitor Alert")
    body = str(payload.get("body") or payload.get("text") or "")
    tags = payload.get("tags") or []

    tag_map: dict[str, str] = {}
    for t in tags:
        if isinstance(t, str) and ":" in t:
            k, _, v = t.partition(":")
            tag_map[k.strip()] = v.strip()

    workload = tag_map.get("service") or tag_map.get("kube_deployment") or "workload"
    namespace = tag_map.get("kube_namespace") or tag_map.get("namespace") or "default"
    environment = tag_map.get("env") or "staging"
    commit_sha = tag_map.get("version") or tag_map.get("commit_sha") or "0000000"
    if len(commit_sha) < 7:
        commit_sha = "0000000"

    repo_owner = tag_map.get("repo_owner") or os.environ.get("RAPHAEL_DEFAULT_REPO_OWNER", "raphael")
    repo_name = tag_map.get("repo_name") or os.environ.get("RAPHAEL_DEFAULT_REPO_NAME", workload)

    # 1. Event Fingerprint
    monitor_id = str(payload.get("monitor_id") or payload.get("id") or "0")
    group_key = str(payload.get("group_key") or tag_map.get("service") or title)
    occurrence = str(payload.get("event_id") or payload.get("id") or monitor_id)
    event_id = build_event_fingerprint("datadog", "monitor", f"{occurrence}:{group_key}")
    run_id = f"run-{uuid.uuid4().hex[:12]}"

    # 2. Canonical Incident Fingerprint
    inc_fp = build_canonical_incident_fingerprint(
        tenant=_tenant_id(),
        service=workload,
        environment=environment,
        release=commit_sha,
        symptom_class=normalize_symptom_class(f"{title} {body}"),
        operation=namespace,
        error_class=normalize_symptom_class(f"{title} {body}"),
        cause_anchor=f"{repo_owner}/{repo_name}",
    )

    resources = [{"kind": "Deployment", "name": workload, "namespace": namespace}]

    seed: dict[str, Any] = {
        "run_id": run_id,
        "tenant_id": _tenant_id(),
        "trigger": {
            "kind": "datadog",
            "event_id": event_id,
            "received_at": utc_now(),
            "raw_ref": f"datadog:{event_id}",
        },
        "repository": {"owner": repo_owner, "name": repo_name},
        "commit_sha": commit_sha,
        "target_environment": environment,
        "failure_fingerprint": inc_fp.canonical_string,
        "affected_resources": resources,
        "correlation": {
            "workload": workload,
            "namespace": namespace,
            "workflow_name": title,
            "check_name": "datadog_monitor",
            "provisional_failure_key": inc_fp.canonical_string,
        },
        "notes": f"{title}\n{body}",
        "runtime_observation": {"reason": f"{title} {body}", "log_window": body},
    }
    seed["failure_fingerprint"] = build_fingerprint(seed)
    return seed


def normalize_cloudwatch_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize an AWS CloudWatch alarm / SNS payload into a Raphael run seed with 3-layer fingerprints."""
    sns_message_id = str(payload.get("MessageId") or "")
    # Unwrap SNS JSON Message envelope if delivered via SNS
    if "Type" in payload and payload.get("Type") == "Notification" and "Message" in payload:
        try:
            msg = json.loads(payload["Message"])
            if isinstance(msg, dict):
                payload = msg
        except (ValueError, TypeError):
            pass

    alarm_name = str(payload.get("AlarmName") or "CloudWatchAlarm")
    alarm_arn = str(payload.get("AlarmArn") or "")
    reason = str(payload.get("NewStateReason") or payload.get("AlarmDescription") or "")
    metric_name = str(payload.get("MetricName") or payload.get("Namespace") or "AWS/ContainerInsights")

    dimensions: dict[str, str] = {}
    dims_raw = payload.get("Dimensions") or []
    if isinstance(dims_raw, list):
        for d in dims_raw:
            if isinstance(d, dict):
                dimensions[str(d.get("name") or d.get("Name"))] = str(d.get("value") or d.get("Value"))
    elif isinstance(dims_raw, dict):
        dimensions = {str(k): str(v) for k, v in dims_raw.items()}

    workload = str(
        dimensions.get("ServiceName")
        or dimensions.get("PodName")
        or dimensions.get("ClusterName")
        or dimensions.get("TargetGroup")
        or "workload"
    )
    environment = str(dimensions.get("Environment") or dimensions.get("Env") or "staging")
    namespace = str(dimensions.get("Namespace") or "default")

    commit_sha = str(dimensions.get("CommitSha") or payload.get("CommitSha") or "0000000")
    if len(commit_sha) < 7:
        commit_sha = "0000000"

    repo_owner = str(dimensions.get("RepoOwner") or os.environ.get("RAPHAEL_DEFAULT_REPO_OWNER", "raphael"))
    repo_name = str(dimensions.get("RepoName") or os.environ.get("RAPHAEL_DEFAULT_REPO_NAME", workload))

    # 1. Event Fingerprint
    state_updated = str(payload.get("StateUpdatedTimestamp") or payload.get("NewStateValue") or "")
    event_id = build_event_fingerprint("cloudwatch", "alarm", f"{alarm_arn or sns_message_id or alarm_name}:{state_updated}")
    run_id = f"run-{uuid.uuid4().hex[:12]}"

    # 2. Canonical Incident Fingerprint
    inc_fp = build_canonical_incident_fingerprint(
        tenant=_tenant_id(),
        service=workload,
        environment=environment,
        release=commit_sha,
        symptom_class=normalize_symptom_class(f"{alarm_name} {reason} {metric_name}"),
        operation=namespace,
        error_class=normalize_symptom_class(f"{alarm_name} {reason} {metric_name}"),
        cause_anchor=f"{repo_owner}/{repo_name}",
    )

    seed: dict[str, Any] = {
        "run_id": run_id,
        "tenant_id": _tenant_id(),
        "trigger": {
            "kind": "cloudwatch",
            "event_id": event_id,
            "received_at": utc_now(),
            "raw_ref": f"cloudwatch:{alarm_name}",
        },
        "repository": {"owner": repo_owner, "name": repo_name},
        "commit_sha": commit_sha,
        "target_environment": environment,
        "failure_fingerprint": inc_fp.canonical_string,
        "affected_resources": [{"kind": "Deployment", "name": workload, "namespace": namespace}],
        "correlation": {
            "workload": workload,
            "namespace": namespace,
            "workflow_name": alarm_name,
            "check_name": "cloudwatch_alarm",
            "provisional_failure_key": inc_fp.canonical_string,
        },
        "notes": f"{alarm_name}: {reason}",
        "runtime_observation": {"reason": reason or alarm_name, "slo": metric_name},
    }
    seed["failure_fingerprint"] = build_fingerprint(seed)
    return seed
