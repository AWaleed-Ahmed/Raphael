"""Option B follow-on tests: CODEOWNERS, SQLite store, App auth config."""

from __future__ import annotations

from pathlib import Path

from raphael_agent.publish.codeowners import parse_codeowners_logins, reviewers_from_codeowners
from raphael_agent.publish.config import github_token, pr_reviewers
from raphael_agent.store import open_run_store


def test_parse_codeowners_skips_teams():
    text = """
* @alice @bob
/docs/ @org/docs-team @carol
"""
    logins = parse_codeowners_logins(text)
    assert "alice" in logins
    assert "bob" in logins
    assert "carol" in logins
    assert "org" not in logins


def test_reviewers_from_codeowners_file(tmp_path: Path, monkeypatch):
    github = tmp_path / ".github"
    github.mkdir()
    (github / "CODEOWNERS").write_text("* @dana @erin\n", encoding="utf-8")
    monkeypatch.setenv("RAPHAEL_CODEOWNERS_WORKSPACE", str(tmp_path))
    assert reviewers_from_codeowners() == ["dana", "erin"]


def test_pr_reviewers_merges_codeowners(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("RAPHAEL_GITHUB_REVIEWERS", "frank")
    monkeypatch.setenv("RAPHAEL_REVIEWERS_FROM_CODEOWNERS", "1")
    (tmp_path / "CODEOWNERS").write_text("* @gina\n", encoding="utf-8")
    monkeypatch.setenv("RAPHAEL_CODEOWNERS_PATH", str(tmp_path / "CODEOWNERS"))
    reviewers = pr_reviewers()
    assert "frank" in reviewers
    assert "gina" in reviewers


def test_github_token_prefers_pat(monkeypatch):
    monkeypatch.setenv("RAPHAEL_GITHUB_TOKEN", "pat-xyz")
    monkeypatch.setenv("RAPHAEL_GITHUB_APP_ID", "1")
    monkeypatch.setenv("RAPHAEL_GITHUB_INSTALLATION_ID", "2")
    assert github_token() == "pat-xyz"


def test_sqlite_run_store_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_STORE", "sqlite")
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    store = open_run_store(tmp_path)
    run = {
        "run_id": "run-sql-1",
        "tenant_id": "local-dev",
        "status": "success_draft_pr_ready",
        "updated_at": "2026-08-10T00:00:00Z",
        "failure_fingerprint": "fp-1",
    }
    store.save_run(run)
    loaded = store.get_run("run-sql-1")
    assert loaded is not None
    assert loaded["run_id"] == "run-sql-1"
    assert (tmp_path / "runs.sqlite3").is_file()
