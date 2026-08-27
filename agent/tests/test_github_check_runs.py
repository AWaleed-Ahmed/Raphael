"""GH-M4 advisory Check Runs (GH-030â€“034)."""

from __future__ import annotations

from pathlib import Path

from raphael_agent.github_commands.check_runs import (
    CHECK_NAME,
    annotations_for_run,
    check_conclusion,
    maybe_complete_check_run,
    maybe_start_check_run,
    render_check_output,
)
from raphael_agent.runs import apply_run_action
from raphael_agent.store import RunStore

AGENT_ROOT = Path(__file__).resolve().parents[1]


class FakeChecks:
    def __init__(self) -> None:
        self.creates: list[dict] = []
        self.updates: list[dict] = []
        self._n = 9000

    def create_check_run(self, owner, repo, **kwargs):
        self._n += 1
        rec = {"id": self._n, "owner": owner, "repo": repo, **kwargs}
        self.creates.append(rec)
        return rec

    def update_check_run(self, owner, repo, **kwargs):
        rec = {"owner": owner, "repo": repo, **kwargs}
        self.updates.append(rec)
        return rec


def _run_record(**overrides) -> dict:
    run = {
        "run_id": "run-abc123",
        "tenant_id": "local-dev",
        "status": "pending",
        "repository": {"owner": "raphael", "name": "demo"},
        "commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
        "created_at": "2026-08-14T00:00:00Z",
        "updated_at": "2026-08-14T00:01:00Z",
        "issue_number": 42,
        "pull_request_number": 42,
        "pull_request_url": "https://github.com/raphael/demo/pull/42",
        "result_id": "res-xyz",
        "diagnosis": {
            "classification": {
                "category": "supported",
                "failure_class": "probe_misconfiguration",
            },
            "confidence": 0.81,
        },
        "publish": {"result_id": "res-xyz"},
        "audit_events": [],
        "trigger": {"kind": "manual_ui", "received_at": "2026-08-14T00:00:00Z"},
        "failure_fingerprint": "fp-demo",
        "sandbox_mode": "skipped",
        "validation_results": [
            {
                "checks": [
                    {
                        "name": "http_probe",
                        "kind": "http",
                        "status": "pass",
                        "duration_ms": 12,
                    }
                ]
            }
        ],
        "candidate_patches": [
            {
                "patch_id": "p1",
                "files": [
                    {
                        "path": "deploy/manifests/app.yaml",
                        "action": "modify",
                        "content": "readinessProbe:\n  httpGet:\n    port: 8080\n",
                    }
                ],
            }
        ],
        "active_patch_id": "p1",
    }
    run.update(overrides)
    return run


def test_knob_off_no_check_api_even_if_commands_on(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_GITHUB_COMMANDS", "1")
    monkeypatch.setenv("RAPHAEL_GITHUB_AUTO_COMMENTS", "1")
    monkeypatch.delenv("RAPHAEL_GITHUB_CHECK_RUNS", raising=False)
    fake = FakeChecks()
    monkeypatch.setattr(
        "raphael_agent.github_commands.check_runs._CLIENT_OVERRIDE", fake
    )
    store = RunStore(tmp_path)
    run = _run_record()
    start = maybe_start_check_run(run, store=store, client=fake)
    done = maybe_complete_check_run(
        {**run, "status": "success_draft_pr_ready"}, store=store, client=fake
    )
    assert start["decision"] == "skipped"
    assert done["decision"] == "skipped"
    assert fake.creates == []
    assert fake.updates == []


def test_create_on_start_update_on_each_terminal(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_GITHUB_CHECK_RUNS", "1")
    monkeypatch.delenv("RAPHAEL_GITHUB_CHECK_ADVISORY_SUCCESS", raising=False)
    fake = FakeChecks()
    store = RunStore(tmp_path)
    terminals = (
        "success_draft_pr_ready",
        "success_fix_proposed",
        "escalated",
        "failed_closed",
    )
    for status in terminals:
        run = _run_record(run_id=f"run-{status}", status="pending")
        started = maybe_start_check_run(run, store=store, client=fake)
        assert started["decision"] == "created"
        assert started["check_run_id"]
        assert fake.creates[-1]["name"] == CHECK_NAME
        assert fake.creates[-1]["status"] == "in_progress"
        assert fake.creates[-1]["head_sha"] == run["commit_sha"]
        assert "advisory" in fake.creates[-1]["output"]["summary"].lower()

        run["status"] = status
        if status == "escalated":
            run["terminal_reason"] = "low_confidence"
        if status == "failed_closed":
            run["terminal_reason"] = "publish_failed"
        done = maybe_complete_check_run(run, store=store, client=fake)
        assert done["decision"] == "updated"
        assert done["conclusion"] == "neutral"
        payload = fake.updates[-1]
        assert payload["check_run_id"] == started["check_run_id"]
        assert payload["status"] == "completed"
        assert payload["conclusion"] == "neutral"
        text = payload["output"]["summary"] + payload["output"]["text"]
        assert run["run_id"] in text
        assert "probe_misconfiguration" in text
        assert "0.81" in text
        assert "res-xyz" in text
        assert "http_probe" in text
        assert "advisory" in text.lower()
        assert "does not replace human review" in text.lower()
        assert "merge" in text.lower()
        assert "Merge action" in text or "never merges" in text.lower()

    assert len(fake.creates) == 4
    assert len(fake.updates) == 4
    sidecar = (tmp_path / "github_check_runs.json").read_text(encoding="utf-8")
    assert "check_run_id" in sidecar
    runs_dir = tmp_path / "runs"
    if runs_dir.is_dir():
        for path in runs_dir.glob("*.json"):
            assert "check_run_id" not in path.read_text(encoding="utf-8")


def test_retry_child_gets_its_own_check(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_GITHUB_CHECK_RUNS", "1")
    monkeypatch.setenv("RAPHAEL_MANUAL_RUN_GRAPH", "0")
    fake = FakeChecks()
    monkeypatch.setattr(
        "raphael_agent.github_commands.check_runs._CLIENT_OVERRIDE", fake
    )
    store = RunStore(tmp_path)
    parent = _run_record(status="success_draft_pr_ready")
    store.save_run(parent)
    maybe_start_check_run(parent, store=store, client=fake)
    maybe_complete_check_run(parent, store=store, client=fake)
    parent_id = fake.creates[-1]["id"]

    result = apply_run_action(
        "run-abc123",
        {
            "verb": "retry",
            "action_id": "chk-retry-1",
            "sandbox_mode": "skipped",
        },
        store=store,
    )
    child_id = result["result_run_id"]
    assert child_id != "run-abc123"
    child_creates = [c for c in fake.creates if c.get("external_id") == child_id]
    assert child_creates
    assert child_creates[0]["id"] != parent_id
    sidecar = store.root / "github_check_runs.json"
    data = sidecar.read_text(encoding="utf-8")
    assert "run-abc123" in data
    assert child_id in data


def test_annotations_allowlisted_paths_only(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_GITHUB_CHECK_RUNS", "1")
    fake = FakeChecks()
    store = RunStore(tmp_path)
    secret = "Authorization: Bearer SUPERSECRETTOKEN"
    run = _run_record(
        status="success_draft_pr_ready",
        candidate_patches=[
            {
                "patch_id": "p1",
                "files": [
                    {
                        "path": "deploy/manifests/app.yaml",
                        "action": "modify",
                        "content": "port: 8080\n",
                    },
                    {
                        "path": "src/main.go",
                        "action": "modify",
                        "content": "package main\n",
                    },
                    {
                        "path": "secrets/prod.env",
                        "action": "modify",
                        "content": "x=1\n",
                    },
                    {
                        "path": "deploy/ok.env",
                        "action": "modify",
                        "content": secret + "\n",
                    },
                ],
            }
        ],
    )
    paths = {a["path"] for a in annotations_for_run(run)}
    assert paths == {"deploy/manifests/app.yaml"}
    assert all(a["annotation_level"] == "notice" for a in annotations_for_run(run))

    maybe_start_check_run({**run, "status": "pending"}, store=store, client=fake)
    done = maybe_complete_check_run(run, store=store, client=fake)
    anns = done["output"]["annotations"]
    assert [a["path"] for a in anns] == ["deploy/manifests/app.yaml"]
    blob = str(fake.updates[-1])
    assert "src/main.go" not in blob
    assert "secrets/prod.env" not in blob
    assert "SUPERSECRETTOKEN" not in blob


def test_conclusion_neutral_unless_advisory_success_opt_in(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_GITHUB_CHECK_RUNS", "1")
    monkeypatch.delenv("RAPHAEL_GITHUB_CHECK_ADVISORY_SUCCESS", raising=False)
    assert check_conclusion("success_draft_pr_ready") == "neutral"
    assert check_conclusion("success_fix_proposed") == "neutral"
    assert check_conclusion("escalated") == "neutral"
    assert check_conclusion("failed_closed") == "neutral"
    monkeypatch.setenv("RAPHAEL_GITHUB_CHECK_ADVISORY_SUCCESS", "1")
    assert check_conclusion("success_draft_pr_ready") == "success"
    assert check_conclusion("success_fix_proposed") == "success"
    assert check_conclusion("escalated") == "neutral"
    assert check_conclusion("failed_closed") == "neutral"

    fake = FakeChecks()
    store = RunStore(tmp_path)
    run = _run_record(status="success_draft_pr_ready")
    maybe_start_check_run({**run, "status": "pending"}, store=store, client=fake)
    done = maybe_complete_check_run(run, store=store, client=fake)
    assert done["conclusion"] == "success"
    assert fake.updates[-1]["conclusion"] == "success"
    assert fake.updates[-1]["conclusion"] != "failure"

    failed = _run_record(run_id="run-fail", status="failed_closed")
    maybe_start_check_run({**failed, "status": "pending"}, store=store, client=fake)
    closed = maybe_complete_check_run(failed, store=store, client=fake)
    assert closed["conclusion"] == "neutral"


def test_check_output_redacts_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_GITHUB_CHECK_RUNS", "1")
    secret = "Authorization: Bearer SUPERSECRETTOKEN"
    run = _run_record(
        status="escalated",
        terminal_reason="human_requested",
        escalation_report={"summary": secret, "why_no_fix": secret},
        diagnosis={
            "classification": {
                "category": "supported",
                "failure_class": "probe_misconfiguration",
            },
            "confidence": 0.81,
        },
    )
    output = render_check_output(run)
    blob = output["title"] + output["summary"] + output["text"]
    assert "SUPERSECRETTOKEN" not in blob
    assert "run-abc123" in blob
    assert "probe_misconfiguration" in blob
    assert CHECK_NAME in output["title"]
    assert "advisory" in output["summary"].lower()

    fake = FakeChecks()
    store = RunStore(tmp_path)
    maybe_start_check_run({**run, "status": "pending"}, store=store, client=fake)
    maybe_complete_check_run(run, store=store, client=fake)
    posted = str(fake.creates) + str(fake.updates)
    assert "SUPERSECRETTOKEN" not in posted


def test_graph_start_then_complete_recorded_stub(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_GITHUB_CHECK_RUNS", "1")
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    fake = FakeChecks()
    monkeypatch.setattr(
        "raphael_agent.github_commands.check_runs._CLIENT_OVERRIDE", fake
    )
    import json

    from raphael_agent.graph import initial_run_state, run_stub_graph
    from raphael_agent.ingest import normalize_failed_run_event

    fixture = AGENT_ROOT / "fixtures" / "failed_run_event.json"
    workspace = (
        AGENT_ROOT.parent
        / "sandbox"
        / "harness"
        / "scenarios"
        / "probe_port_mismatch"
    )
    event = json.loads(fixture.read_text(encoding="utf-8"))
    event["workspace_path"] = str(workspace)
    seed = normalize_failed_run_event(event)
    seed["workspace_path"] = event["workspace_path"]
    seed["manifests"] = event.get("manifests")
    initial = initial_run_state(seed, sandbox_mode="recorded_stub")
    final = run_stub_graph(initial)
    assert fake.creates, "graph start should POST a Check Run"
    assert fake.creates[0]["name"] == CHECK_NAME
    assert fake.creates[0]["status"] == "in_progress"
    assert fake.updates, "terminal publish should PATCH the Check Run"
    assert fake.updates[-1]["status"] == "completed"
    assert fake.updates[-1]["conclusion"] == "neutral"
    assert fake.updates[-1]["conclusion"] != "failure"
    assert final["status"] in {
        "success_draft_pr_ready",
        "success_fix_proposed",
        "escalated",
        "failed_closed",
    }
