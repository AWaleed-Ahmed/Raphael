from raphael_agent.telemetry_supabase import (
    SupabaseTelemetryStore,
    build_run_outcome_event,
    record_run_outcome,
    resolve_company_id,
)


def test_upload_adds_normalized_scope(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(request, timeout):
        captured["body"] = request.data
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("raphael_agent.telemetry_supabase.urlopen", fake_urlopen)
    store = SupabaseTelemetryStore("https://example.supabase.co", "secret")
    count = store.upload(
        [{"event_id": "event-1", "event_type": "run_outcome", "project_name": "payments"}],
        company_id="company-1",
        client_id="client-1",
    )

    assert count == 1
    assert '"company_id": "company-1"' in captured["body"].decode()
    assert '"client_id": "client-1"' in captured["body"].decode()


def test_build_run_outcome_event_is_terminal_and_redacted():
    event = build_run_outcome_event(
        {
            "run_id": "run-1",
            "status": "failed_closed",
            "updated_at": "2026-08-21T10:00:00+00:00",
            "terminal_reason": "publish_failed",
            "repository": {"owner": "acme", "name": "payments"},
            "trigger": {"kind": "github_workflow_run"},
            "delivery_mode": "draft_pr",
            "sandbox_mode": "recorded_stub",
            "errors": [{"code": "publish_failed", "message": "secret-value"}],
            "input_excerpt": "must-not-be-copied",
            "output_excerpt": "must-not-be-copied",
        }
    )

    assert event == {
        "event_id": "run-1:run_outcome:failed_closed",
        "event_type": "run_outcome",
        "project_name": "acme/payments",
        "run_id": "run-1",
        "recorded_at": "2026-08-21T10:00:00+00:00",
        "repository": {"owner": "acme", "name": "payments"},
        "status": "failed_closed",
        "success": False,
        "metadata": {
            "trigger_kind": "github_workflow_run",
            "delivery_mode": "draft_pr",
            "sandbox_mode": "recorded_stub",
            "terminal_reason": "publish_failed",
        },
        "error_type": "publish_failed",
    }
    assert "secret-value" not in str(event)
    assert build_run_outcome_event({"run_id": "run-2", "status": "running"}) is None


def test_terminal_event_id_is_stable_for_duplicate_safe_uploads():
    run = {
        "run_id": "run-1",
        "status": "cancelled",
        "repository": {"owner": "acme", "name": "payments"},
    }
    first = build_run_outcome_event(run)
    second = build_run_outcome_event(run)
    assert first is not None
    assert first["event_id"] == second["event_id"]


def test_record_run_outcome_is_failure_safe_without_scope(monkeypatch):
    monkeypatch.delenv("RAPHAEL_COMPANY_ID", raising=False)
    monkeypatch.delenv("RAPHAEL_CLIENT_ID", raising=False)
    assert record_run_outcome({"run_id": "run-1", "status": "cancelled"}) is False



def test_resolve_company_id_prefers_explicit_and_environment(monkeypatch):
    monkeypatch.setenv("RAPHAEL_COMPANY_ID", "env-company")
    assert resolve_company_id("client-1", "explicit-company") == "explicit-company"
    assert resolve_company_id("client-1") == "env-company"


def test_resolve_company_id_uses_client_catalog(monkeypatch):
    monkeypatch.delenv("RAPHAEL_COMPANY_ID", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'[{"company_id":"catalog-company","client_id":"client-1","status":"active"}]'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("raphael_agent.telemetry_supabase.urlopen", fake_urlopen)
    assert resolve_company_id("client-1") == "catalog-company"
    assert "client_id=eq.client-1" in captured["url"]


def test_resolve_company_id_returns_none_without_scope(monkeypatch):
    monkeypatch.delenv("RAPHAEL_COMPANY_ID", raising=False)
    monkeypatch.delenv("RAPHAEL_CLIENT_ID", raising=False)
    assert resolve_company_id(None) is None


def test_record_run_outcome_skips_safely_when_upload_fails(monkeypatch):
    monkeypatch.setenv("RAPHAEL_COMPANY_ID", "company-1")
    monkeypatch.setenv("RAPHAEL_CLIENT_ID", "client-1")

    class BrokenStore:
        def upload(self, *_args, **_kwargs):
            raise RuntimeError("network failure")

    monkeypatch.setattr("raphael_agent.telemetry_supabase.SupabaseTelemetryStore", BrokenStore)
    assert record_run_outcome(
        {
            "run_id": "run-failure-safe",
            "status": "cancelled",
            "repository": {"owner": "acme", "name": "payments"},
        }
    ) is False
