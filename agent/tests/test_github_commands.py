"""GH-M1 GitHub-native slash commands (parse, ACL, rate limit, idempotency)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from raphael_agent.feedback import JsonlFeedbackRecorder
from raphael_agent.github_commands.acl import acl_allows
from raphael_agent.github_commands.handler import extract_run_id_markers, handle_issue_comment_event
from raphael_agent.github_commands.idempotency import CommandIdempotencyStore
from raphael_agent.github_commands.parse import parse_command
from raphael_agent.github_commands.rate_limit import CommandRateLimiter
from raphael_agent.http_api import create_app
from raphael_agent.schema_util import validate_agent
from raphael_agent.store import RunStore

AGENT_ROOT = Path(__file__).resolve().parents[1]


def _payload(
    *,
    body: str = "/raphael status",
    login: str = "alice",
    association: str = "COLLABORATOR",
    comment_id: int = 1001,
    number: int = 42,
    issue_body: str = "",
    is_pr: bool = True,
    user_type: str = "User",
    action: str = "created",
) -> dict:
    issue: dict = {
        "number": number,
        "body": issue_body,
        "html_url": f"https://github.com/raphael/demo/issues/{number}",
    }
    if is_pr:
        issue["html_url"] = f"https://github.com/raphael/demo/pull/{number}"
        issue["pull_request"] = {"html_url": issue["html_url"]}
    return {
        "action": action,
        "issue": issue,
        "comment": {
            "id": comment_id,
            "body": body,
            "user": {"login": login, "type": user_type},
            "author_association": association,
        },
        "repository": {"name": "demo", "owner": {"login": "raphael"}},
        "sender": {"login": login},
    }


def _run_record(**overrides) -> dict:
    run = {
        "run_id": "run-abc123",
        "tenant_id": "local-dev",
        "status": "success_draft_pr_ready",
        "repository": {"owner": "raphael", "name": "demo"},
        "commit_sha": "abcdef1234567",
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
    }
    run.update(overrides)
    return run


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_GITHUB_COMMANDS", "1")
    monkeypatch.delenv("RAPHAEL_GITHUB_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("RAPHAEL_INTERFACE_TOKEN", raising=False)
    monkeypatch.delenv("RAPHAEL_GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_FEEDBACK_RECORDER", "jsonl")
    return TestClient(create_app())


def _post_comment(client: TestClient, payload: dict, delivery: str = "deliv-1"):
    return client.post(
        "/v1/webhooks/github",
        content=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "issue_comment",
            "X-GitHub-Delivery": delivery,
        },
    )


def test_parse_verbs_and_feedback_grammar():
    status = parse_command("/raphael status run-abc123")
    assert status is not None
    assert status.verb == "status"
    assert status.args == ("run-abc123",)
    assert status.implemented is True

    help_cmd = parse_command("Please\n/raphael help\n")
    assert help_cmd is not None and help_cmd.verb == "help"

    fb = parse_command("/raphael feedback rejected extra notes")
    assert fb is not None
    assert fb.verb == "feedback"
    assert fb.outcome == "rejected"
    assert fb.implemented is True

    accept = parse_command("/raphael accept")
    assert accept is not None
    assert accept.error == "unknown_verb"

    missing = parse_command("/raphael feedback")
    assert missing is not None and missing.error == "feedback_missing_outcome"

    bad = parse_command("/raphael feedback merged")
    assert bad is not None and bad.error == "feedback_invalid_outcome"

    retry = parse_command("/raphael retry")
    assert retry is not None
    assert retry.verb == "retry"
    assert retry.implemented is False
    assert retry.privileged is True

    assert parse_command("not a command") is None
    empty = parse_command("/raphael")
    assert empty is not None
    assert empty.error == "missing_verb"


def test_parse_custom_prefix():
    parsed = parse_command("/fixbot status", prefix="/fixbot")
    assert parsed is not None
    assert parsed.verb == "status"


def test_acl_write_allow_privileged_deny():
    assert acl_allows("status", association="COLLABORATOR", login="alice")
    assert acl_allows("help", association="MEMBER", login="alice")
    assert acl_allows("feedback", association="OWNER", login="alice")
    assert not acl_allows("status", association="NONE", login="mallory")
    assert not acl_allows("retry", association="COLLABORATOR", login="alice")
    assert acl_allows("retry", association="OWNER", login="alice")
    assert acl_allows(
        "escalate",
        association="NONE",
        login="bob",
        team_logins=frozenset({"bob"}),
    )
    assert not acl_allows(
        "fix",
        association="COLLABORATOR",
        login="alice",
        team_logins=frozenset({"oncall"}),
    )


def test_rate_limit_per_repo_actor(tmp_path: Path):
    limiter = CommandRateLimiter(tmp_path / "rate.json", limit=2)
    assert limiter.allow("raphael", "demo", "alice")[0] is True
    assert limiter.allow("raphael", "demo", "alice")[0] is True
    allowed, remaining = limiter.allow("raphael", "demo", "alice")
    assert allowed is False
    assert remaining == 0
    assert limiter.allow("raphael", "demo", "bob")[0] is True


def test_idempotent_store_comment_and_delivery(tmp_path: Path):
    store = CommandIdempotencyStore(tmp_path / "idemp.json")
    store.put({"decision": "replied", "verb": "help"}, comment_id="9", delivery_id="d1")
    assert store.get(comment_id="9", delivery_id="other")["verb"] == "help"
    assert store.get(comment_id="nope", delivery_id="d1")["verb"] == "help"


def test_extract_run_id_markers():
    html = "hello\n<!-- raphael:run_id=run-html -->\n"
    footer = "see raphael:run_id=run-footer\n"
    assert extract_run_id_markers(html) == "run-html"
    assert extract_run_id_markers(footer) == "run-footer"
    assert extract_run_id_markers(html, footer) == "run-footer"


def test_commands_disabled_does_not_parse(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_GITHUB_COMMANDS", "0")
    monkeypatch.delenv("RAPHAEL_GITHUB_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("RAPHAEL_FEEDBACK_RECORDER", "jsonl")
    client = TestClient(create_app())
    resp = _post_comment(
        client, _payload(body="/raphael feedback rejected", comment_id=77)
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["decision"] == "ignored"
    assert "RAPHAEL_GITHUB_COMMANDS" in body["reason"]
    assert "verb" not in body
    assert not (tmp_path / "feedback.jsonl").is_file()


def test_ignore_bot_self_comment(client):
    resp = _post_comment(
        client,
        _payload(
            body="/raphael status",
            login="raphael-agent[bot]",
            user_type="Bot",
            association="OWNER",
        ),
    )
    assert resp.status_code == 202
    assert resp.json()["decision"] == "ignored"
    assert "self-comment" in resp.json()["reason"]


def test_http_acl_deny_privileged(client):
    resp = _post_comment(
        client,
        _payload(body="/raphael retry", association="COLLABORATOR", comment_id=3),
        delivery="acl-deny-1",
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["decision"] == "denied"
    assert data["verb"] == "retry"
    assert "admin" in data["reply"].lower() or "team" in data["reply"].lower()


def test_http_rate_limit(client, monkeypatch):
    monkeypatch.setenv("RAPHAEL_GITHUB_COMMAND_RATE_LIMIT", "2")
    payload = _payload(body="/raphael help", comment_id=10)
    assert _post_comment(client, payload, delivery="rl-1").json()["decision"] == "replied"
    payload2 = _payload(body="/raphael help", comment_id=11)
    assert _post_comment(client, payload2, delivery="rl-2").json()["decision"] == "replied"
    payload3 = _payload(body="/raphael help", comment_id=12)
    third = _post_comment(client, payload3, delivery="rl-3")
    assert third.status_code == 202
    assert third.json()["decision"] == "rate_limited"


def test_idempotent_duplicate_delivery_feedback(client, tmp_path):
    payload = _payload(
        body="/raphael feedback rejected",
        comment_id=55,
        association="COLLABORATOR",
        is_pr=True,
        number=12,
    )
    first = _post_comment(client, payload, delivery="dup-1")
    second = _post_comment(client, payload, delivery="dup-1")
    assert first.status_code == 202
    assert first.json()["decision"] == "replied"
    assert first.json()["feedback_event_id"]
    assert second.json().get("idempotent_replay") is True
    rows = JsonlFeedbackRecorder(tmp_path / "feedback.jsonl").read_all()
    assert len(rows) == 1
    validate_agent(
        "feedback_event.json",
        {k: v for k, v in rows[0].items() if v is not None},
    )
    assert rows[0]["outcome"] == "rejected"
    assert rows[0]["source"] == "github_webhook"
    assert rows[0]["pull_request_number"] == 12
    assert rows[0]["actor"] == "alice"


def test_status_happy_paths(client, tmp_path):
    store = RunStore(tmp_path)
    store.save_run(_run_record())

    explicit = _post_comment(
        client,
        _payload(body="/raphael status run-abc123", comment_id=21, number=99),
        delivery="st-explicit",
    )
    assert explicit.status_code == 202
    reply = explicit.json()["reply"]
    assert explicit.json()["run_id"] == "run-abc123"
    assert "run-abc123" in reply
    assert "success_draft_pr_ready" in reply
    assert "probe_misconfiguration" in reply
    assert "partner=dry_run" in reply
    assert "publish=dry_run" in reply
    assert "ghp_" not in reply
    assert "RAPHAEL_GITHUB_TOKEN" not in reply

    marker = _post_comment(
        client,
        _payload(
            body="/raphael status",
            comment_id=22,
            number=7,
            issue_body="notes\n<!-- raphael:run_id=run-abc123 -->\n",
        ),
        delivery="st-marker",
    )
    assert marker.json()["run_id"] == "run-abc123"
    assert "### Raphael run `run-abc123`" in marker.json()["reply"]

    lookup = _post_comment(
        client,
        _payload(body="/raphael status", comment_id=23, number=42),
        delivery="st-lookup",
    )
    assert lookup.json()["run_id"] == "run-abc123"
    assert "draft PR → https://github.com/raphael/demo/pull/42" in lookup.json()["reply"]


def test_help_lists_verbs_and_mode_no_secrets(client):
    resp = _post_comment(
        client, _payload(body="/raphael help", comment_id=30), delivery="help-1"
    )
    reply = resp.json()["reply"]
    assert resp.json()["decision"] == "replied"
    assert "status" in reply
    assert "help" in reply
    assert "feedback" in reply
    assert "retry" in reply
    assert "deferred" in reply.lower() or "not implemented" in reply.lower()
    assert "partner=dry_run" in reply
    assert "publish=dry_run" in reply
    assert "RAPHAEL_INTERFACE_TOKEN" not in reply
    assert "RAPHAEL_GITHUB_TOKEN" not in reply


def test_deferred_privileged_verb_does_not_retry(client, tmp_path):
    store = RunStore(tmp_path)
    store.save_run(_run_record())
    resp = _post_comment(
        client,
        _payload(body="/raphael retry", association="OWNER", comment_id=40),
        delivery="def-1",
    )
    assert resp.json()["decision"] == "deferred"
    assert "not implemented" in resp.json()["reply"].lower()
    assert len(store.list_runs()) == 1


def test_no_sandbox_imports_in_command_package():
    combined = ""
    for path in (AGENT_ROOT / "raphael_agent" / "github_commands").glob("*.py"):
        combined += path.read_text(encoding="utf-8")
    assert "sandbox_client" not in combined
    assert "RAPHAEL_SANDBOX_URL" not in combined


def test_feedback_visible_as_fr065_event(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_FEEDBACK_RECORDER", "jsonl")
    store = RunStore(tmp_path)
    store.save_run(_run_record())
    result = handle_issue_comment_event(
        _payload(body="/raphael feedback rejected", comment_id=88, is_pr=True),
        delivery_id="fb-direct",
        store=store,
    )
    assert result["decision"] == "replied"
    rows = JsonlFeedbackRecorder(tmp_path / "feedback.jsonl").read_all()
    assert rows[0]["outcome"] == "rejected"
    assert rows[0]["run_id"] == "run-abc123"
    validate_agent(
        "feedback_event.json",
        {k: v for k, v in rows[0].items() if v is not None},
    )
