"""Budget exhaust paths — never publish."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from raphael_agent.budgets import build_budget_snapshot, check_budgets
from raphael_agent.graph.nodes import node_diagnose, node_publish_or_escalate
from raphael_agent.graph.state import initial_run_state


def _seed_state(**overrides):
    state = initial_run_state(
        {
            "run_id": "budget-1",
            "tenant_id": "local-dev",
            "trigger": {
                "kind": "fixture",
                "event_id": "e",
                "received_at": "2026-08-10T12:00:00Z",
            },
            "repository": {"owner": "raphael", "name": "demo"},
            "commit_sha": "abcdef1234567",
        },
        sandbox_mode="recorded_stub",
    )
    state.update(overrides)
    return state


def test_wall_clock_budget_halts(monkeypatch):
    monkeypatch.setenv("RAPHAEL_MAX_WALL_SECONDS", "1")
    past = (datetime.now(timezone.utc) - timedelta(seconds=5)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    state = _seed_state(
        budget_snapshot={
            **build_budget_snapshot(),
            "deadline_at": past,
            "max_wall_seconds": 1,
        },
        status="running",
        result_id="res-should-not-publish",
        validation_results=[
            {
                "sandbox_id": "sb",
                "passed": True,
                "fail_closed": False,
                "full_validation": True,
                "checks": [],
                "completed_at": "2026-08-10T12:00:00Z",
            }
        ],
    )
    updates = node_publish_or_escalate(state)
    assert updates["status"] == "escalated"
    assert updates["terminal_reason"] == "budget_exhausted"
    assert updates.get("pull_request_url") is None


def test_diagnosis_attempt_budget(monkeypatch):
    monkeypatch.setenv("RAPHAEL_MAX_DIAGNOSIS_ATTEMPTS", "1")
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    state = _seed_state(
        budget_snapshot={
            **build_budget_snapshot(),
            "max_diagnosis_attempts": 1,
        },
        attempt_count={"diagnosis": 1, "patch": 0},
        status="running",
        evidence=[
            {
                "evidence_id": "ev-1",
                "kind": "ci_log",
                "source": {"system": "fixture", "ref": "t"},
                "summary": "x",
                "content_excerpt": "unclear failure",
                "redacted": True,
                "provenance": {"collector": "t", "query": "t"},
                "collected_at": "2026-08-10T12:00:00Z",
            }
        ],
    )
    updates = node_diagnose(state)
    assert updates["status"] == "escalated"
    assert updates["terminal_reason"] == "budget_exhausted"
    assert "publish" not in updates or updates.get("pull_request_url") is None


def test_cost_ceiling(monkeypatch):
    monkeypatch.setenv("RAPHAEL_MAX_COST_USD", "1.0")
    snap = build_budget_snapshot()
    snap["max_cost_usd"] = 1.0
    halt = check_budgets(
        {
            "budget_snapshot": snap,
            "attempt_count": {"diagnosis": 0, "patch": 0},
            "token_and_cost_usage": {"model_tokens": 0, "estimated_cost_usd": 2.5},
        },
        node="diagnose",
    )
    assert halt is not None
    assert halt["kind"] == "cost"
    assert halt["terminal"] == "escalated"
