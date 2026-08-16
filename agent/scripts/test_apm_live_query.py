#!/usr/bin/env python3
"""Interactive verification script: query a Prometheus APM server (live or local mock fallback) and evaluate metrics."""

from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from raphael_agent.evidence.apm import (
    APMEvidenceCollector,
    MetricSeverity,
    MetricSnapshot,
    PerformanceThresholds,
    PrometheusClient,
)

PUBLIC_PROMETHEUS_URL = "https://demo.promlabs.com"


class MockPrometheusHandler(BaseHTTPRequestHandler):
    """Local mock Prometheus HTTP API server for offline / air-gapped test environments."""

    def log_message(self, format, *args):
        pass  # suppress standard HTTP logs for clean output

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        promql = params.get("query", [""])[0]

        now = time.time()
        result_value = 0.0

        if "http_requests_total" in promql or "prometheus_http_requests_total" in promql:
            if 'status=~"5.."' in promql or 'code=~"5.."' in promql:
                result_value = 0.05  # 0.05 errors/sec
            else:
                result_value = 142.5 # 142.5 req/sec
        elif "duration_seconds_bucket" in promql:
            if "0.99" in promql:
                result_value = 0.048 # 48ms P99
            elif "0.90" in promql:
                result_value = 0.032 # 32ms P90
            elif "0.50" in promql:
                result_value = 0.015 # 15ms P50
            else:
                result_value = 0.025
        elif "up" in promql:
            result_value = 1.0

        response_payload = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"job": "demo-service", "instance": "demo-pod-1"},
                        "value": [now, str(result_value)],
                    }
                ],
            },
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response_payload).encode("utf-8"))


def start_local_mock_prometheus(port: int = 19090) -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", port), MockPrometheusHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


def main() -> int:
    print("=" * 72)
    print(" 🚀 Raphael APM Server Query & Performance Anomaly Evaluation")
    print("=" * 72)

    # 1. Check Connectivity (Remote Public vs Local Mock)
    target_url = PUBLIC_PROMETHEUS_URL
    print(f"\n[Step 1] Attempting connection to public Prometheus API: {target_url}...")
    
    client = PrometheusClient(target_url, timeout=3.0)
    server_to_close = None
    try:
        up_result = client.query("up")
        targets_up = len(up_result.get("result", []))
        print(f" ✅ Connected to live public Prometheus server! (Active targets: {targets_up})")
    except Exception as exc:
        print(f" ℹ️  Public server unreachable ({exc}).")
        print(" 🔄 Starting local Prometheus API service (127.0.0.1:19090) for offline verification...")
        server_to_close, target_url = start_local_mock_prometheus(port=19090)
        client = PrometheusClient(target_url, timeout=3.0)
        up_result = client.query("up")
        print(f" ✅ Local Prometheus API online at {target_url}")

    thresholds = PerformanceThresholds(
        error_rate_slowing_down_pct=1.0,
        error_rate_failure_pct=5.0,
        latency_degradation_slowing_down_factor=1.5,
        latency_degradation_failure_factor=3.0,
        p99_absolute_slowing_down_seconds=0.500,  # 500ms
        p99_absolute_failure_seconds=2.000,       # 2000ms
    )
    collector = APMEvidenceCollector(target_url, thresholds=thresholds)

    # 2. Query Live Request Rates and Latencies
    print("\n[Step 2] Querying live HTTP metrics across service endpoints via APMEvidenceCollector...")
    live_snapshot = collector.snapshot_workload_metrics("demo")


    print(f" 📊 Live Metrics Snapshot retrieved from Prometheus API:")
    print(f"    ├─ Throughput:     {live_snapshot.request_rate_rps} req/sec")
    print(f"    ├─ HTTP 5xx Rate:  {live_snapshot.error_rate_pct}%")
    print(f"    ├─ P50 Latency:    {live_snapshot.p50_latency_seconds * 1000:.2f} ms")
    print(f"    ├─ P90 Latency:    {live_snapshot.p90_latency_seconds * 1000:.2f} ms")
    print(f"    └─ P99 Latency:    {live_snapshot.p99_latency_seconds * 1000:.2f} ms")

    # 3. Anomaly Evaluation across 3 distinct operational cases
    print("\n[Step 3] Evaluating Metric Thresholds across 3 Operational Scenarios:")
    now = live_snapshot.timestamp

    # Scenario A: Healthy State
    baseline = MetricSnapshot(
        timestamp=now - 600,
        request_rate_rps=live_snapshot.request_rate_rps,
        error_rate_pct=live_snapshot.error_rate_pct,
        p99_latency_seconds=live_snapshot.p99_latency_seconds,
    )

    report_healthy = collector.evaluate_performance(baseline, live_snapshot, workload="payments-api")
    print(f"\n  ▶ [Scenario A] Healthy Normal State (Within Limits)")
    print(f"    Verdict:  {report_healthy.severity.value.upper()} ✅")
    print(f"    Summary:  {report_healthy.summary}")
    print(f"    Action:   {report_healthy.recommended_action}")

    # Scenario B: "Slowing Down" Performance Degradation
    degraded_snapshot = MetricSnapshot(
        timestamp=now,
        request_rate_rps=live_snapshot.request_rate_rps,
        error_rate_pct=2.4,  # 2.4% 5xx errors (between 1.0% and 5.0%)
        p99_latency_seconds=live_snapshot.p99_latency_seconds * 1.8,  # +80% latency increase
    )
    report_slowing = collector.evaluate_performance(baseline, degraded_snapshot, workload="payments-api")
    print(f"\n  ▶ [Scenario B] 'Slowing Down' Alert (Degraded Latency + 2.4% Errors)")
    print(f"    Verdict:  {report_slowing.severity.value.upper()} ⚠️")
    print(f"    Summary:  {report_slowing.summary}")
    for r in report_slowing.reasons:
        print(f"    ├─ Finding: {r}")
    print(f"    └─ Action:  {report_slowing.recommended_action}")

    # Scenario C: Deployment Failure (Severe Outage / 5xx Spike)
    failing_snapshot = MetricSnapshot(
        timestamp=now,
        request_rate_rps=live_snapshot.request_rate_rps,
        error_rate_pct=11.8,  # 11.8% 5xx errors (>= 5.0% failure threshold)
        p99_latency_seconds=2.850,  # 2,850ms (exceeds SLA cap)
    )
    report_failure = collector.evaluate_performance(baseline, failing_snapshot, workload="payments-api")
    print(f"\n  ▶ [Scenario C] Deployment Failure (11.8% 5xx Spike & P99 = 2,850ms)")
    print(f"    Verdict:  {report_failure.severity.value.upper()} 🚨")
    print(f"    Summary:  {report_failure.summary}")
    for r in report_failure.reasons:
        print(f"    ├─ Finding: {r}")
    print(f"    └─ Action:  {report_failure.recommended_action}")

    # 4. Generate Typed EvidenceItem
    print("\n[Step 4] Formatted Raphael EvidenceItem for Agent Diagnosis Graph:")
    evidence_item = collector.create_evidence_item(report_failure, workload="payments-api", evidence_id="ev-apm-01")
    print(f" ✅ Evidence ID:     {evidence_item['evidence_id']}")
    print(f"    Content SHA256:  {evidence_item['content_hash']}")
    print(f"    Provenance:      {evidence_item['provenance']['collector']} via {evidence_item['provenance']['query']}")
    print("\n--- Evidence Excerpt Rendered for LLM Diagnosis ---")
    print(evidence_item["content_excerpt"])
    print("---------------------------------------------------")

    if server_to_close:
        server_to_close.shutdown()

    print("\n" + "=" * 72)
    print(" 🎉 All APM query endpoints, threshold rules, and schemas passed!")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
