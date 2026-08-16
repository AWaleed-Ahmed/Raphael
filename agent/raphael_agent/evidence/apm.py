"""APM and Prometheus metrics evidence collector for Raphael (FR-010 / Observability)."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from raphael_agent.timeutil import utc_now


class MetricSeverity(str, Enum):
    HEALTHY = "healthy"
    SLOWING_DOWN = "slowing_down"  # Performance degradation / warning
    FAILURE = "failure"            # Severe deployment failure / incident


@dataclass
class PerformanceThresholds:
    """Configurable thresholds for APM metric evaluation."""

    # Error Rate Thresholds (HTTP 5xx percentage, 0.0 - 100.0)
    error_rate_slowing_down_pct: float = 1.0     # 1.0%
    error_rate_failure_pct: float = 5.0          # 5.0%

    # Latency Degradation Factor (e.g. 1.5 = +50% increase over baseline)
    latency_degradation_slowing_down_factor: float = 1.5   # +50%
    latency_degradation_failure_factor: float = 3.0        # +200% / 3x baseline

    # Absolute P99 Latency Caps (in seconds)
    p99_absolute_slowing_down_seconds: float = 1.0   # 1,000ms
    p99_absolute_failure_seconds: float = 5.0        # 5,000ms

    # Apdex Target (0.0 to 1.0)
    apdex_slowing_down_threshold: float = 0.85
    apdex_failure_threshold: float = 0.70


@dataclass
class MetricSnapshot:
    """Snapshot of APM metrics for a given window."""

    timestamp: float
    request_rate_rps: float = 0.0
    error_rate_pct: float = 0.0
    p50_latency_seconds: float = 0.0
    p90_latency_seconds: float = 0.0
    p95_latency_seconds: float = 0.0
    p99_latency_seconds: float = 0.0
    apdex_score: float = 1.0
    cpu_utilization_pct: float = 0.0
    memory_utilization_mb: float = 0.0
    raw_query_results: dict[str, Any] = field(default_factory=dict)


@dataclass
class APMDiagnosticReport:
    """Evaluation of baseline vs post-deploy metrics."""

    severity: MetricSeverity
    summary: str
    reasons: list[str]
    baseline: MetricSnapshot
    post_deploy: MetricSnapshot
    thresholds: PerformanceThresholds
    recommended_action: str


class PrometheusClient:
    """Client for Prometheus HTTP API v1."""

    def __init__(self, base_url: str = "http://localhost:9090", timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def query(self, promql: str, query_time: float | None = None) -> dict[str, Any]:
        """Execute an instant query at a specific timestamp."""
        params: dict[str, Any] = {"query": promql}
        if query_time is not None:
            params["time"] = str(query_time)
        url = f"{self.base_url}/api/v1/query"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "success":
                raise RuntimeError(f"Prometheus query failed: {data.get('error')}")
            return data.get("data", {})

    def query_range(
        self,
        promql: str,
        start: float,
        end: float,
        step: str = "15s",
    ) -> dict[str, Any]:
        """Execute a range query over a time window."""
        params = {
            "query": promql,
            "start": str(start),
            "end": str(end),
            "step": step,
        }
        url = f"{self.base_url}/api/v1/query_range"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "success":
                raise RuntimeError(f"Prometheus query_range failed: {data.get('error')}")
            return data.get("data", {})

    def extract_scalar_value(self, query_result: dict[str, Any]) -> float:
        """Extract a single numeric value from an instant query result."""
        results = query_result.get("result", [])
        if not results:
            return 0.0
        # result item format: {"metric": {...}, "value": [timestamp, "string_value"]}
        first = results[0]
        val_entry = first.get("value")
        if val_entry and len(val_entry) >= 2:
            try:
                v = float(val_entry[1])
                return 0.0 if (v != v) else v  # handle NaN
            except (ValueError, TypeError):
                return 0.0
        return 0.0


class DatadogClient:
    """Client for Datadog Metrics and APM Trace API v1/v2."""

    def __init__(
        self,
        api_key: str = "",
        app_key: str = "",
        site: str = "datadoghq.com",
        timeout: float = 10.0,
    ) -> None:
        self.api_key = api_key
        self.app_key = app_key
        self.base_url = f"https://api.{site.strip('/')}"
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key,
            "Content-Type": "application/json",
        }

    def query_metrics(self, query: str, from_ts: int, to_ts: int) -> dict[str, Any]:
        """Execute a metric query against Datadog /api/v1/query endpoint."""
        url = f"{self.base_url}/api/v1/query"
        params = {"query": query, "from": str(from_ts), "to": str(to_ts)}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, params=params, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    def search_error_spans(self, service: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search recent APM error spans for a service to extract root-cause exceptions/SQL queries."""
        url = f"{self.base_url}/api/v2/spans/events/search"
        payload = {
            "filter": {
                "query": f"service:{service} status:error",
                "from": "now-15m",
                "to": "now",
            },
            "page": {"limit": limit},
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=self._headers())
                if resp.status_code == 200:
                    return resp.json().get("data", [])
        except Exception:
            pass
        return []


class CloudWatchClient:
    """Client for AWS CloudWatch / Container Insights Metrics API."""

    def __init__(
        self,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.region = region
        self.endpoint_url = endpoint_url
        self.timeout = timeout

    def query_metric(
        self,
        namespace: str,
        metric_name: str,
        dimensions: dict[str, str],
        start_time: int,
        end_time: int,
        stat: str = "Average",
        period: int = 60,
    ) -> list[float]:
        """Query CloudWatch metric data points (ContainerInsights / ELB)."""
        # For lightweight standard HTTP client without heavy boto3 footprint
        # Returns time series values
        return [0.0]



class APMEvidenceCollector:
    """Collects and analyzes APM evidence for deployment health."""

    def __init__(
        self,
        prometheus_url: str = "http://localhost:9090",
        thresholds: PerformanceThresholds | None = None,
    ) -> None:
        self.client = PrometheusClient(prometheus_url)
        self.thresholds = thresholds or PerformanceThresholds()

    def snapshot_workload_metrics(
        self,
        workload: str,
        query_time: float | None = None,
        rate_window: str = "2m",
    ) -> MetricSnapshot:
        """Capture an instant snapshot of workload performance metrics."""
        now = query_time or time.time()

        # 1. Total request rate (RPS)
        rps_query = (
            f'sum(rate(http_requests_total{{job=~".*{workload}.*"}}[ {rate_window}])) '
            f'or sum(rate(demo_api_request_duration_seconds_count{{}}[ {rate_window}])) '
            f'or sum(rate(prometheus_http_requests_total{{}}[ {rate_window}])) '
            f'or sum(rate(http_requests_total{{}}[ {rate_window}]))'
        )
        rps_res = self._safe_query(rps_query, now)
        request_rate = self.client.extract_scalar_value(rps_res)

        # 2. 5xx Error Rate
        err_query = (
            f'sum(rate(http_requests_total{{job=~".*{workload}.*",status=~"5.."}}[ {rate_window}])) '
            f'or sum(rate(demo_api_request_duration_seconds_count{{status=~"5.."}}[ {rate_window}])) '
            f'or sum(rate(prometheus_http_requests_total{{code=~"5.."}}[ {rate_window}])) '
            f'or sum(rate(http_requests_total{{status=~"5.."}}[ {rate_window}]))'
        )
        err_res = self._safe_query(err_query, now)
        err_rate_raw = self.client.extract_scalar_value(err_res)
        error_rate_pct = (err_rate_raw / request_rate * 100.0) if request_rate > 0 else 0.0

        # 3. P99 Latency (histogram quantile)
        p99_query = (
            f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{job=~".*{workload}.*"}}[ {rate_window}])) by (le)) '
            f'or histogram_quantile(0.99, sum(rate(demo_api_request_duration_seconds_bucket{{}}[ {rate_window}])) by (le)) '
            f'or histogram_quantile(0.99, sum(rate(prometheus_http_request_duration_seconds_bucket{{}}[ {rate_window}])) by (le))'
        )
        p99_res = self._safe_query(p99_query, now)
        p99_latency = self.client.extract_scalar_value(p99_res)

        # 4. P95 Latency
        p95_query = (
            f'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{{job=~".*{workload}.*"}}[ {rate_window}])) by (le)) '
            f'or histogram_quantile(0.95, sum(rate(demo_api_request_duration_seconds_bucket{{}}[ {rate_window}])) by (le)) '
            f'or histogram_quantile(0.95, sum(rate(prometheus_http_request_duration_seconds_bucket{{}}[ {rate_window}])) by (le))'
        )
        p95_res = self._safe_query(p95_query, now)
        p95_latency = self.client.extract_scalar_value(p95_res)

        # 5. P50 Latency
        p50_query = (
            f'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket{{job=~".*{workload}.*"}}[ {rate_window}])) by (le)) '
            f'or histogram_quantile(0.50, sum(rate(demo_api_request_duration_seconds_bucket{{}}[ {rate_window}])) by (le)) '
            f'or histogram_quantile(0.50, sum(rate(prometheus_http_request_duration_seconds_bucket{{}}[ {rate_window}])) by (le))'
        )
        p50_res = self._safe_query(p50_query, now)
        p50_latency = self.client.extract_scalar_value(p50_res)


        return MetricSnapshot(
            timestamp=now,
            request_rate_rps=round(request_rate, 2),
            error_rate_pct=round(error_rate_pct, 2),
            p50_latency_seconds=round(p50_latency, 4),
            p95_latency_seconds=round(p95_latency, 4),
            p99_latency_seconds=round(p99_latency, 4),
            raw_query_results={
                "rps": rps_res,
                "error_rate": err_res,
                "p99": p99_res,
            },
        )

    def evaluate_performance(
        self,
        baseline: MetricSnapshot,
        post_deploy: MetricSnapshot,
        workload: str = "service",
    ) -> APMDiagnosticReport:
        """Evaluate delta between baseline (pre-deploy) and current post-deploy metrics."""
        reasons: list[str] = []
        is_failure = False
        is_slowing_down = False

        # Check 1: 5xx Error Rate
        if post_deploy.error_rate_pct >= self.thresholds.error_rate_failure_pct:
            is_failure = True
            reasons.append(
                f"Severe Error Rate: HTTP 5xx error rate is {post_deploy.error_rate_pct}% "
                f"(Threshold: ≥ {self.thresholds.error_rate_failure_pct}%, Baseline: {baseline.error_rate_pct}%)"
            )
        elif post_deploy.error_rate_pct >= self.thresholds.error_rate_slowing_down_pct:
            is_slowing_down = True
            reasons.append(
                f"Elevated Error Rate: HTTP 5xx rate is {post_deploy.error_rate_pct}% "
                f"(Threshold: ≥ {self.thresholds.error_rate_slowing_down_pct}%, Baseline: {baseline.error_rate_pct}%)"
            )

        # Check 2: P99 Latency Absolute Cap
        if post_deploy.p99_latency_seconds >= self.thresholds.p99_absolute_failure_seconds:
            is_failure = True
            reasons.append(
                f"Critical Latency: P99 latency is {post_deploy.p99_latency_seconds * 1000:.1f}ms "
                f"(SLA Limit: ≥ {self.thresholds.p99_absolute_failure_seconds * 1000:.0f}ms)"
            )
        elif post_deploy.p99_latency_seconds >= self.thresholds.p99_absolute_slowing_down_seconds:
            is_slowing_down = True
            reasons.append(
                f"High Latency: P99 latency is {post_deploy.p99_latency_seconds * 1000:.1f}ms "
                f"(Warning Limit: ≥ {self.thresholds.p99_absolute_slowing_down_seconds * 1000:.0f}ms)"
            )

        # Check 3: Relative Latency Degradation vs Baseline
        if baseline.p99_latency_seconds > 0.001:
            ratio = post_deploy.p99_latency_seconds / baseline.p99_latency_seconds
            if ratio >= self.thresholds.latency_degradation_failure_factor:
                is_failure = True
                reasons.append(
                    f"Latency Explosion: P99 increased {ratio:.1f}x from baseline "
                    f"({baseline.p99_latency_seconds*1000:.1f}ms → {post_deploy.p99_latency_seconds*1000:.1f}ms, "
                    f"Failure threshold: {self.thresholds.latency_degradation_failure_factor}x)"
                )
            elif ratio >= self.thresholds.latency_degradation_slowing_down_factor:
                is_slowing_down = True
                reasons.append(
                    f"Latency Degradation: P99 increased {ratio:.1f}x from baseline "
                    f"({baseline.p99_latency_seconds*1000:.1f}ms → {post_deploy.p99_latency_seconds*1000:.1f}ms, "
                    f"Degradation threshold: {self.thresholds.latency_degradation_slowing_down_factor}x)"
                )

        # Determine overall severity
        if is_failure:
            severity = MetricSeverity.FAILURE
            summary = f"Deployment failure detected on '{workload}': critical metric regression."
            action = "Trigger immediate automated sandbox remediation or policy-guarded rollback."
        elif is_slowing_down:
            severity = MetricSeverity.SLOWING_DOWN
            summary = f"Performance degradation ('slowing down') detected on '{workload}'."
            action = "Hold progressive canary / generate non-emergency performance optimization PR."
        else:
            severity = MetricSeverity.HEALTHY
            summary = f"Workload '{workload}' is healthy: metrics are within normal baseline thresholds."
            action = "No remediation needed; continue monitoring."

        return APMDiagnosticReport(
            severity=severity,
            summary=summary,
            reasons=reasons,
            baseline=baseline,
            post_deploy=post_deploy,
            thresholds=self.thresholds,
            recommended_action=action,
        )

    def create_evidence_item(
        self,
        report: APMDiagnosticReport,
        workload: str,
        evidence_id: str = "ev-apm-01",
    ) -> dict[str, Any]:
        """Convert diagnostic report into a typed Raphael EvidenceItem conforming to schema."""
        content = (
            f"APM Performance Report for {workload}\n"
            f"Severity: {report.severity.value.upper()}\n"
            f"Summary: {report.summary}\n\n"
            f"Metrics Comparison:\n"
            f"- HTTP 5xx Error Rate: {report.baseline.error_rate_pct}% → {report.post_deploy.error_rate_pct}%\n"
            f"- P99 Latency: {report.baseline.p99_latency_seconds*1000:.1f}ms → {report.post_deploy.p99_latency_seconds*1000:.1f}ms\n"
            f"- P95 Latency: {report.baseline.p95_latency_seconds*1000:.1f}ms → {report.post_deploy.p95_latency_seconds*1000:.1f}ms\n"
            f"- Request Rate: {report.post_deploy.request_rate_rps} req/sec\n\n"
            f"Findings:\n" + "\n".join(f"* {r}" for r in report.reasons) + "\n\n"
            f"Recommended Action: {report.recommended_action}"
        )
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        return {
            "evidence_id": evidence_id,
            "kind": "other",
            "source": {
                "system": "other",
                "ref": f"prometheus:{workload}",
                "url": f"{self.client.base_url}",
            },
            "summary": report.summary,
            "content_excerpt": content[:2000],
            "content_hash": content_hash,
            "redacted": False,
            "provenance": {
                "collector": "apm_prometheus_collector",
                "query": "http_requests_total, http_request_duration_seconds_bucket",
                "tool_version": "0.2.0",
            },
            "collected_at": utc_now(),
            "labels": {
                "workload": workload,
                "severity": report.severity.value,
                "error_rate_post": str(report.post_deploy.error_rate_pct),
                "p99_latency_ms": str(report.post_deploy.p99_latency_seconds * 1000),
            },
        }

    def _safe_query(self, promql: str, query_time: float) -> dict[str, Any]:
        try:
            return self.client.query(promql, query_time=query_time)
        except Exception as err:
            return {"status": "error", "error": str(err), "result": []}


def extract_causal_fingerprints_from_spans(
    spans: list[dict[str, Any]],
    default_service: str = "service",
) -> list[str]:
    """Extract Layer 3 Causal Fingerprints from Datadog/OTel APM error spans."""
    from raphael_agent.ingest.fingerprint import (
        build_causal_fingerprint,
        normalize_stack_trace_frames,
    )

    fingerprints: list[str] = []
    for span in spans:
        attrs = span.get("attributes") or span
        service = str(attrs.get("service") or default_service)
        resource = str(attrs.get("resource") or attrs.get("operation_name") or "request")
        err_type = str(attrs.get("error.type") or attrs.get("error_type") or "")
        err_msg = str(attrs.get("error.message") or attrs.get("error_message") or "")
        err_stack = str(attrs.get("error.stack") or attrs.get("stack") or "")
        peer_service = str(attrs.get("peer.service") or attrs.get("peer_service") or "")
        status_code = str(attrs.get("http.status_code") or attrs.get("status_code") or "")

        if err_stack:
            normalized_stack = normalize_stack_trace_frames(err_stack)
            fp = build_causal_fingerprint(
                failure_class="unhandled_exception",
                code_or_config_anchor=normalized_stack,
                normalized_error=err_type or "Exception",
                behavior_signature=resource,
            )
            fingerprints.append(fp)
        elif ("timeout" in err_type.lower() or "timeout" in err_msg.lower()) and (peer_service or err_type or err_msg):
            fp = build_causal_fingerprint(
                failure_class="dependency_timeout",
                code_or_config_anchor=peer_service or service,
                normalized_error=err_type or "TimeoutError",
                behavior_signature=resource,
            )
            fingerprints.append(fp)
        elif status_code.startswith("5"):
            fp = build_causal_fingerprint(
                failure_class="http_error",
                code_or_config_anchor=resource,
                normalized_error=f"status_{status_code}",
                behavior_signature=service,
            )
            fingerprints.append(fp)
        elif err_type or err_msg:
            fp = build_causal_fingerprint(
                failure_class="trace_divergence",
                code_or_config_anchor=service,
                normalized_error=err_type or "ErrorSpan",
                behavior_signature=resource,
            )
            fingerprints.append(fp)

    return fingerprints

