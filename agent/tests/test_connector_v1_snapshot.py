"""Guard the evidence boundary: this work must not alter connector-v1 bytes."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


EXPECTED_SHA256 = {
    "ack.schema.json": "9dff43bdbeab67b941f6dbe77492ea02f4900863fa31bea9bc6c56dd99bd3675",
    "action.schema.json": "46a59eea3e826ca1fef367d381a6f881dccc72e680ea097ef4016f6c6a608238",
    "envelope.schema.json": "62665135852cac0ca79de4c881562cc263ced1f9da47a4d2f6cd14cc3ed55919",
    "error.schema.json": "911ac2f23905f5e402fc797992e23053b36b74153360d9e2ca506993edad6540",
    "job.schema.json": "89ec68894ba99c1bf35436ba5df4b5d4a8e4aad8fe9ecfea4ef70ae9e5f4a94c",
    "result.schema.json": "bf4e1e4639f559f75d06b49b592f8b342ff7c92e5bf351511d31967c330840fb",
    "terminal.schema.json": "176a53afb358f2cd5401ba6a34b8d6cb00feb114194fb996746eeb1d7b49d9b1",
}


def test_connector_v1_public_schema_bytes_are_unchanged() -> None:
    repo = Path(__file__).resolve().parents[2]
    root = repo / "contracts" / "sandbox" / "connector" / "v1"
    actual = {}
    for path in sorted(root.glob("*.json")):
        # Hash exact committed bytes, independent of core.autocrlf checkout
        # conversion. Also reject local edits, not just committed schema drift.
        blob = subprocess.check_output(
            ["git", "show", f"HEAD:{path.relative_to(repo).as_posix()}"], cwd=repo
        )
        assert path.read_bytes() in (blob, blob.replace(b"\n", b"\r\n")), path.name
        actual[path.name] = hashlib.sha256(blob).hexdigest()
    assert actual == EXPECTED_SHA256
