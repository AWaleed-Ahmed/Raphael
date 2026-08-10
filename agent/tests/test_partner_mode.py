"""Partner mode + live failure-class allowlist."""

from __future__ import annotations

from unittest.mock import MagicMock

from raphael_agent.publish import publish
from raphael_agent.publish.config import effective_publish_mode, partner_mode
from tests.test_publish import _base_run


def test_partner_dry_run_default(monkeypatch):
    monkeypatch.delenv("RAPHAEL_PARTNER_MODE", raising=False)
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "live")
    monkeypatch.setenv("RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES", "probe_misconfiguration")
    assert partner_mode() == "dry_run"
    assert effective_publish_mode(_base_run()) == "dry_run"
    result = publish(_base_run())
    assert result["ok"] is True
    assert result["dry_run"] is True


def test_allowlist_empty_forces_dry_run(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "allowlist")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "live")
    monkeypatch.setenv("RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES", "")
    monkeypatch.setenv("RAPHAEL_GITHUB_TOKEN", "t")
    assert effective_publish_mode(_base_run()) == "dry_run"
    result = publish(_base_run())
    assert result["dry_run"] is True


def test_allowlist_class_enables_live(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "allowlist")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "live")
    monkeypatch.setenv("RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES", "probe_misconfiguration")
    monkeypatch.setenv("RAPHAEL_GITHUB_TOKEN", "test-token")
    assert effective_publish_mode(_base_run()) == "live"
    gh = MagicMock()
    gh.get_ref_sha.return_value = "sha"
    gh.find_open_pr.return_value = None
    gh.create_draft_pr.return_value = {
        "html_url": "https://github.com/raphael/demo/pull/9",
        "number": 9,
    }
    result = publish(_base_run(), github=gh)
    assert result["ok"] is True
    assert result["dry_run"] is False
    assert result["mode"] == "live"


def test_allowlist_other_class_stays_dry(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "allowlist")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "live")
    monkeypatch.setenv("RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES", "bad_image_reference")
    run = _base_run()
    assert effective_publish_mode(run) == "dry_run"


def test_diagnosis_only_partner_mode(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "diagnosis_only")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "live")
    result = publish(_base_run())
    assert result["dry_run"] is True
    assert "diagnosis_only" in result["message"]
