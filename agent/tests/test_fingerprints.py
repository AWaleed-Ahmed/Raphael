"""Unit tests for the 3-Layer Fingerprinting Engine (Event, Incident, Causal)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from raphael_agent.evidence.apm import extract_causal_fingerprints_from_spans
from raphael_agent.http_api.app import create_app
from raphael_agent.ingest.apm_webhook import (
    normalize_alertmanager_webhook,
    normalize_cloudwatch_webhook,
    normalize_datadog_webhook,
)
from raphael_agent.ingest.fingerprint import (
    build_canonical_incident_fingerprint,
    build_causal_fingerprint,
    build_event_fingerprint,
    normalize_stack_trace_frames,
    sanitize_fingerprint_text,
)
from raphael_agent.schema_util import validate_sandbox
from raphael_agent.store import RunStore


def test_event_fingerprint_generation():
    """Layer 1: Verify event deduplication keys across providers."""
    dd_event = build_event_fingerprint("datadog", "monitor", "847392:group-checkout-prod")
    assert dd_event == "datadog:monitor:847392:group-checkout-prod"

    prom_event = build_event_fingerprint("alertmanager", "alert", "prod/checkout/ApmPerformanceAlert")
    assert prom_event == "alertmanager:alert:prod/checkout/apmperformancealert"

    cw_event = build_event_fingerprint("cloudwatch", "alarm", "arn:aws:cloudwatch:us-east-1:123456:alarm:Target5XXHigh")
    assert "cloudwatch:alarm:arn:aws:cloudwatch:us-east-1:123456:alarm:target5xxhigh" in cw_event



def test_exclusion_filters_noise_stripping():
    """Verify timestamps, memory addresses, pod UUIDs, and request IDs are sanitized out."""
    noisy_text = (
        "Pod payments-api-7b89f6d-x9z2q failed at 2026-08-15T21:58:13.123Z with error at 0x7ffee231 "
        "handling req_abc123456789"
    )
    clean = sanitize_fingerprint_text(noisy_text)
    assert "7b89f6d" not in clean
    assert "2026-08-15" not in clean
    assert "0x7ffee231" not in clean
    assert "req_abc123456789" not in clean
    assert "<POD_SUFFIX>" in clean
    assert "<TIME>" in clean
    assert "<MEM_ADDR>" in clean
    assert "<REQ_ID>" in clean


def test_cross_provider_canonical_incident_unification():
    """Layer 2: Verify Prometheus, Datadog, and AWS produce the identical canonical incident key."""
    tenant = "acme-corp"
    service = "checkout-api"
    env = "production"
    release = "a1b2c3d4e5f6"
    symptom = "high_latency"
    op = "prod"
    err = "p99_gt_2000ms"
    anchor = "acme/checkout"

    # 1. Prometheus Alertmanager incident key
    prom_inc = build_canonical_incident_fingerprint(
        tenant=tenant,
        service=service,
        environment=env,
        release=release,
        symptom_class=symptom,
        operation=op,
        error_class=err,
        cause_anchor=anchor,
    )

    # 2. Datadog Monitor incident key with different case/spaces
    dd_inc = build_canonical_incident_fingerprint(
        tenant="  acme-corp  ",
        service="checkout-api",
        environment="PRODUCTION",
        release="a1b2c3d4e5f6789",  # Truncates to 12 chars
        symptom_class="high_latency",
        operation="prod",
        error_class="p99_gt_2000ms",
        cause_anchor="acme/checkout",
    )

    # 3. AWS CloudWatch incident key
    cw_inc = build_canonical_incident_fingerprint(
        tenant="acme-corp",
        service="checkout-api",
        environment="production",
        release="a1b2c3d4e5f6",
        symptom_class="high_latency",
        operation="prod",
        error_class="p99_gt_2000ms",
        cause_anchor="acme/checkout",
    )

    # All three must have the exact same canonical string and SHA-256 digest!
    assert prom_inc.canonical_string == dd_inc.canonical_string == cw_inc.canonical_string
    assert prom_inc.sha256_hash == dd_inc.sha256_hash == cw_inc.sha256_hash
    assert prom_inc.canonical_string.startswith("v1|acme-corp|checkout-api|production|a1b2c3d4e5f6|high_latency|prod|p99_gt_2000ms|acme/checkout")


def test_causal_fingerprint_generation():
    """Layer 3: Verify Causal Fingerprint generation for sandbox verification."""
    causal_key = build_causal_fingerprint(
        failure_class="dependency_timeout",
        code_or_config_anchor="payment_client.py:84:payment_authorize",
        normalized_error="TimeoutError",
        behavior_signature="POST /orders",
    )
    assert "dependency_timeout:payment_client.py:84:payment_authorize:timeouterror:post /orders" == causal_key


def test_stack_trace_normalization():
    """Verify python exception stack traces are extracted into compact file:line:func anchors."""
    stack_trace = """
Traceback (most recent call last):
  File "/app/server.py", line 42, in handle_request
    response = checkout_controller.process(req)
  File "/app/controllers/checkout.py", line 88, in process
    return payment_gateway.charge(order)
  File "/app/services/payment_gateway.py", line 124, in charge
    raise ConnectionRefusedError("Redis pool exhausted at 0x7ffe391")
"""
    normalized = normalize_stack_trace_frames(stack_trace, max_frames=3)
    assert normalized == "server.py:42:handle_request|checkout.py:88:process|payment_gateway.py:124:charge"


def test_datadog_span_to_causal_fingerprints():
    """Verify APM spans are transformed into typed Causal Fingerprints."""
    spans = [
        {
            "attributes": {
                "service": "checkout",
                "resource": "POST /api/checkout",
                "error": 1,
                "error.type": "TimeoutError",
                "error.message": "Payment gateway timed out after 5000ms",
                "error.stack": 'File "/app/payment_client.py", line 84, in payment_authorize\n  raise TimeoutError()',
            }
        },
        {
            "attributes": {
                "service": "orders",
                "resource": "GET /orders/123",
                "http.status_code": 504,
            }
        },
    ]

    causal_fps = extract_causal_fingerprints_from_spans(spans)
    assert len(causal_fps) == 2
    assert "unhandled_exception:payment_client.py:84:payment_authorize:timeouterror:post /api/checkout" in causal_fps[0]
    assert "http_error:get /orders/123:status_504:orders" in causal_fps[1]


def test_aws_sns_unwrapping_in_cloudwatch_normalizer():
    """Verify SNS JSON message string is unpacked and normalized into 3-layer run seed."""
    sns_envelope = {
        "Type": "Notification",
        "MessageId": "msg-12345",
        "TopicArn": "arn:aws:sns:us-east-1:12345:CloudWatchAlarms",
        "Message": json.dumps({
            "AlarmName": "HighTarget5XX",
            "AlarmDescription": "HTTP 5xx rate > 5%",
            "Namespace": "AWS/ApplicationELB",
            "Dimensions": [
                {"name": "ServiceName", "value": "auth-service"},
                {"name": "CommitSha", "value": "c8d9e0f1a2b3"},
                {"name": "Environment", "value": "production"},
            ],
        }),
    }

    seed = normalize_cloudwatch_webhook(sns_envelope)
    assert seed["trigger"]["kind"] == "cloudwatch"
    assert seed["commit_sha"] == "c8d9e0f1a2b3"
    assert seed["affected_resources"][0]["name"] == "auth-service"
    assert seed["correlation"]["provisional_failure_key"].startswith("v1|")


def test_sandbox_failure_signature_schema_validation():
    """Verify expanded failure_signature.json schema validates new APM and latency failure classes."""
    instance = {
        "class": "latency_regression",
        "key": "latency_regression:checkout_api:p99_gt_2000ms:orders_post",
        "normalized": {
            "reason": "P99 latency > 2000ms",
            "resource_kind": "Deployment",
            "resource_name": "checkout-api",
            "attributes": {
                "p99_ms": 2450.0,
                "error_rate_pct": 0.5,
            },
        },
        "reproduced": True,
        "confidence": 0.95,
        "evidence_refs": [{"kind": "apm_metric", "id": "ev-apm-01"}],
        "observed_at": "2026-08-15T21:58:13Z",
    }
    # Validate against JSON schema in contracts/sandbox/failure_signature.json
    validate_sandbox("failure_signature.json", instance)

