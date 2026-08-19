from pathlib import Path

from raphael_agent.telemetry import record_model_call, record_run_outcome


def test_telemetry_is_normalized_scoped_and_redacted(tmp_path: Path):
    run = {
        "run_id": "run-fake-1",
        "client_name": "Acme",
        "repository": {"owner": "acme", "name": "payments"},
        "status": "success_fix_proposed",
    }
    model = record_model_call(
        run,
        model_name="fake-model",
        model_version="test-1",
        input_payload={"evidence": "Authorization: Bearer SUPERSECRET"},
        output_payload={"classification": "probe_misconfiguration"},
        success=True,
        root=tmp_path,
    )
    outcome = record_run_outcome(run, root=tmp_path)
    assert model["event_type"] == "model_call"
    assert model["client_name"] == "Acme"
    assert model["project_name"] == "payments"
    assert "SUPERSECRET" not in model["input_excerpt"]
    assert len(model["input_sha256"]) == 64
    assert outcome["event_type"] == "run_outcome"
    assert outcome["success"] is True
    assert len((tmp_path / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()) == 2
