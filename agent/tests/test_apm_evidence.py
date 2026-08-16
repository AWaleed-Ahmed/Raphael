"""Unit tests for APM evidence collector, anomaly detection, and Alertmanager ingestion."""

from __future__ import annotations

import time
import pytest
from starlette.testclient import TestClient

from raphael_agent.evidence.apm import (
    APMEvidenceCollector,
    MetricSeverity,
    MetricSnapshot,
    PerformanceThresholds,
    PrometheusClient,
)
from raphael_agent.http_api.app import create_app
from raphael_agent.ingest.apm_webhook import normalize_alertmanager_webhook
from raphael_agent.schema_util import validate_agent
from raphael_agent.store import RunStore


def test_apm_evaluation_healthy():
    collector = APMEvidenceCollector(thresholds=PerformanceThresholds())
    now = time.time()

    baseline = MetricSnapshot(
        timestamp=now - 300,
        request_rate_rps=100.0,
        error_rate_pct=0.05,
        p50_latency_seconds=0.020,
        p95_latency_seconds=0.045,
        p99_latency_seconds=0.060,
    )
    post_deploy = MetricSnapshot(
        timestamp=now,
        request_rate_rps=105.0,
        error_rate_pct=0.08,
        p50_latency_seconds=0.022,
        p95_latency_seconds=0.048,
        p99_latency_seconds=0.065,
    )

    report = collector.evaluate_performance(baseline, post_deploy, workload="payments-api")
    assert report.severity == MetricSeverity.HEALTHY
    assert "healthy" in report.summary.lower()
    assert len(report.reasons) == 0


def test_apm_evaluation_slowing_down_latency():
    collector = APMEvidenceCollector(thresholds=PerformanceThresholds())
    now = time.time()

    baseline = MetricSnapshot(
        timestamp=now - 300,
        request_rate_rps=100.0,
        error_rate_pct=0.0,
        p99_latency_seconds=0.100,  # 100ms
    )
    post_deploy = MetricSnapshot(
        timestamp=now,
        request_rate_rps=100.0,
        error_rate_pct=0.0,
        p99_latency_seconds=0.180,  # 180ms (+80% increase -> >1.5x)
    )

    report = collector.evaluate_performance(baseline, post_deploy, workload="payments-api")
    assert report.severity == MetricSeverity.SLOWING_DOWN
    assert any("Latency Degradation" in r for r in report.reasons)
    assert "slowing down" in report.summary.lower()


def test_apm_evaluation_slowing_down_error_rate():
    collector = APMEvidenceCollector(thresholds=PerformanceThresholds())
    now = time.time()

    baseline = MetricSnapshot(
        timestamp=now - 300,
        request_rate_rps=100.0,
        error_rate_pct=0.0,
        p99_latency_seconds=0.050,
    )
    post_deploy = MetricSnapshot(
        timestamp=now,
        request_rate_rps=100.0,
        error_rate_pct=2.5,  # 2.5% (between 1.0% and 5.0%)
        p99_latency_seconds=0.055,
    )

    report = collector.evaluate_performance(baseline, post_deploy, workload="payments-api")
    assert report.severity == MetricSeverity.SLOWING_DOWN
    assert any("Elevated Error Rate" in r for r in report.reasons)


def test_apm_evaluation_failure_error_spike():
    collector = APMEvidenceCollector(thresholds=PerformanceThresholds())
    now = time.time()

    baseline = MetricSnapshot(
        timestamp=now - 300,
        request_rate_rps=100.0,
        error_rate_pct=0.1,
        p99_latency_seconds=0.050,
    )
    post_deploy = MetricSnapshot(
        timestamp=now,
        request_rate_rps=95.0,
        error_rate_pct=8.4,  # 8.4% (>= 5.0% failure threshold)
        p99_latency_seconds=0.060,
    )

    report = collector.evaluate_performance(baseline, post_deploy, workload="payments-api")
    assert report.severity == MetricSeverity.FAILURE
    assert any("Severe Error Rate" in r for r in report.reasons)
    assert "failure detected" in report.summary.lower()


def test_apm_evaluation_failure_latency_explosion():
    collector = APMEvidenceCollector(thresholds=PerformanceThresholds())
    now = time.time()

    baseline = MetricSnapshot(
        timestamp=now - 300,
        request_rate_rps=100.0,
        error_rate_pct=0.0,
        p99_latency_seconds=0.050,  # 50ms
    )
    post_deploy = MetricSnapshot(
        timestamp=now,
        request_rate_rps=90.0,
        error_rate_pct=0.0,
        p99_latency_seconds=0.250,  # 250ms (5x increase -> >3.0x failure threshold)
    )

    report = collector.evaluate_performance(baseline, post_deploy, workload="payments-api")
    assert report.severity == MetricSeverity.FAILURE
    assert any("Latency Explosion" in r for r in report.reasons)


def test_apm_create_evidence_item_schema():
    collector = APMEvidenceCollector()
    now = time.time()

    baseline = MetricSnapshot(
        timestamp=now - 300,
        request_rate_rps=50.0,
        error_rate_pct=0.0,
        p99_latency_seconds=0.040,
    )
    post_deploy = MetricSnapshot(
        timestamp=now,
        request_rate_rps=48.0,
        error_rate_pct=7.5,
        p99_latency_seconds=0.120,
    )

    report = collector.evaluate_performance(baseline, post_deploy, workload="auth-service")
    item = collector.create_evidence_item(report, workload="auth-service")

    # Validate against frozen JSON Schema
    validate_agent("evidence_item.json", item)
    assert item["kind"] == "other"
    assert item["source"]["system"] == "other"
    assert "auth-service" in item["summary"]
    assert item["labels"]["severity"] == "failure"


def test_alertmanager_webhook_normalization():
    payload = {
        "version": "4",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighHttp5xxRate",
                    "service": "checkout-api",
                    "namespace": "prod",
                    "severity": "critical",
                    "repo_owner": "myorg",
                    "repo_name": "checkout",
                    "commit_sha": "abc987654321",
                },
                "annotations": {
                    "summary": "5xx error rate is 6.8%",
                },
            }
        ],
    }
    seed = normalize_alertmanager_webhook(payload)
    assert seed["trigger"]["kind"] == "alertmanager"
    assert seed["repository"]["owner"] == "myorg"
    assert seed["repository"]["name"] == "checkout"
    assert seed["commit_sha"] == "abc987654321"
    assert seed["affected_resources"][0]["name"] == "checkout-api"
    assert seed["affected_resources"][0]["namespace"] == "prod"


def test_alertmanager_http_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_AUTO_RUN_GRAPH", "0")
    client = TestClient(create_app())

    payload = {
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "LatencySpike",
                    "service": "orders-api",
                    "namespace": "staging",
                    "commit_sha": "def123456789",
                },
                "annotations": {
                    "summary": "P99 latency > 2000ms",
                },
            }
        ]
    }
    resp = client.post("/v1/webhooks/alertmanager", json=payload)
    assert resp.status_code == 202
    data = resp.json()
    assert data["ingest"]["decision"] == "accepted"
    assert data["run_id"].startswith("run-")

    store = RunStore(tmp_path)
    run = store.get_run(data["run_id"])
    assert run is not None
    assert run["trigger"]["kind"] == "alertmanager"
    assert run["commit_sha"] == "def123456789"


def test_datadog_http_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_AUTO_RUN_GRAPH", "0")
    client = TestClient(create_app())

    payload = {
        "id": "123456789",
        "title": "High Latency Alert",
        "body": "P99 latency has exceeded 3,000ms",
        "tags": [
            "service:billing-service",
            "kube_namespace:production",
            "env:production",
            "version:git-sha-7890",
        ],
    }
    resp = client.post("/v1/webhooks/datadog", json=payload)
    assert resp.status_code == 202
    data = resp.json()
    assert data["ingest"]["decision"] == "accepted"
    assert data["run_id"].startswith("run-")

    store = RunStore(tmp_path)
    run = store.get_run(data["run_id"])
    assert run is not None
    assert run["trigger"]["kind"] == "datadog"
    assert run["commit_sha"] == "git-sha-7890"
    assert run["affected_resources"][0]["name"] == "billing-service"


def test_cloudwatch_http_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_AUTO_RUN_GRAPH", "0")
    client = TestClient(create_app())

    payload = {
        "AlarmName": "Target5XXCountHigh",
        "NewStateReason": "Threshold Crossed: HTTPCode_Target_5XX_Count > 50",
        "Namespace": "AWS/ApplicationELB",
        "Dimensions": [
            {"name": "ServiceName", "value": "auth-api"}
        ],
    }
    resp = client.post("/v1/webhooks/cloudwatch", json=payload)
    assert resp.status_code == 202
    data = resp.json()
    assert data["ingest"]["decision"] == "accepted"
    assert data["run_id"].startswith("run-")

    store = RunStore(tmp_path)
    run = store.get_run(data["run_id"])
    assert run is not None
    assert run["trigger"]["kind"] == "cloudwatch"
    assert run["affected_resources"][0]["name"] == "auth-api"


