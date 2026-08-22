from raphael_agent.validation import evaluate_validation_signals


def test_correctness_signals():
    checks = evaluate_validation_signals(
        [
            {"type": "business_invariant", "path": "payment.status", "expected": "settled"},
            {"type": "checksum", "path": "result"},
            {"type": "queue_side_effect", "count_path": "queue.count", "minimum_delta": 1},
            {"type": "golden_trace", "expected_spans": ["request", "db"]},
            {"type": "slo", "path": "latency_ms", "max": 200},
        ],
        baseline={"result": {"total": 1}, "queue": {"count": 1}},
        current={"payment": {"status": "settled"}, "result": {"total": 1}, "queue": {"count": 2}, "span_sequence": ["request", "db"], "latency_ms": 100},
    )
    assert len(checks) == 5
    assert all(item["status"] == "passed" for item in checks)
