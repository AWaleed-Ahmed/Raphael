"""Test-only audit must not read while a background writer truncates the file."""
import importlib.util
import json
from pathlib import Path
import threading


def test_audit_holds_existing_lock_across_save_and_read(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("audit_under_test", Path(__file__).resolve().parents[2]
                                                / "tools/report_audit/escalation_report_audit.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)

    class FakeStore:
        def __init__(self):
            self._lock = threading.RLock()

        def save_run(self, run):
            assert self._lock._is_owned()
            self.run = run

        def get_run(self, run_id):
            assert self._lock._is_owned()
            return self.run

    monkeypatch.setattr(audit, "RunStore", FakeStore)
    monkeypatch.setattr(audit, "SqliteRunStore", FakeStore)
    destination = tmp_path / "audit.jsonl"
    monkeypatch.setenv("RAPHAEL_REPORT_AUDIT_FILE", str(destination))
    audit.install()
    FakeStore().save_run({"run_id": "audit-test", "unknown": "seeded-private-value"})
    record = json.loads(destination.read_text())
    assert record["checks"][0]["errors"]
    assert "seeded-private-value" not in destination.read_text()
