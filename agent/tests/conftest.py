import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_agent_data_dir(monkeypatch, tmp_path):
    """Give every test a fresh RAPHAEL_AGENT_DATA_DIR to prevent
    persistent RunStore fingerprint dedup from causing cross-test
    contamination.  Tests that already set this env var via their own
    monkeypatch will override this fixture's value (pytest applies
    function-scoped monkeypatches after autouse fixtures)."""
    data_dir = tmp_path / "agent-data"
    data_dir.mkdir()
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(data_dir))
