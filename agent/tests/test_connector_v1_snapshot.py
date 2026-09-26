"""Guard the evidence boundary: this work must not alter connector-v1 bytes."""

from __future__ import annotations

import hashlib
from pathlib import Path


EXPECTED_SHA256 = {
    "ack.schema.json": "32400496d55e7677523823eb0ecdd1e5d23167951b09063d9e3eea319bb7c58f",
    "action.schema.json": "8d27673f9026b5bd885aeae2ee3d98f001d6c9c15a5246984266ce487d5d881b",
    "envelope.schema.json": "f6d77e1a82a75c66cba59dc68ed426279d35379ef40c7478a4198e4748bbc534",
    "error.schema.json": "759c6ce635a38cdd29aaa531091ff58892adef39583ca755c2b390088ac71609",
    "job.schema.json": "00838f6ae20521f9ba9e82e285492cf0298507a0b3b738f0e5fddc63bcd2f554",
    "result.schema.json": "b265426ad73ee9c8a1ae7b0f2ca5e93ea55223ef1584ad34db55d61ca69e4195",
    "terminal.schema.json": "bad10a0a8365a208e80eb9cfa1e93476e6129bb12c303ba910f8e47ff7e32a1e",
}


def test_connector_v1_public_schema_bytes_are_unchanged() -> None:
    root = Path(__file__).resolve().parents[2] / "contracts" / "sandbox" / "connector" / "v1"
    actual = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(root.glob("*.json"))}
    assert actual == EXPECTED_SHA256
