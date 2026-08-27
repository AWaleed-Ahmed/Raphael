from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker, RefResolver
from jsonschema.validators import validator_for


PROTOCOL_VERSION = "1.0"
ALLOWED_VERBS = (
    "create_sandbox",
    "deploy_revision",
    "observe_failure",
    "run_validation",
    "finalize_result",
    "destroy_sandbox",
)
KIND_TO_SCHEMA = {
    "job": "job.schema.json",
    "action": "action.schema.json",
    "result": "result.schema.json",
    "ack": "ack.schema.json",
    "terminal": "terminal.schema.json",
    "error": "error.schema.json",
}
VERB_TO_REQUEST = {verb: f"{verb}.request.json" for verb in ALLOWED_VERBS}
VERB_TO_RESPONSE = {verb: f"{verb}.response.json" for verb in ALLOWED_VERBS}
SCHEMA_FILES = (
    "envelope.schema.json",
    "job.schema.json",
    "action.schema.json",
    "result.schema.json",
    "terminal.schema.json",
    "ack.schema.json",
    "error.schema.json",
)


class ProtocolValidationError(ValueError):
    """Raised when a connector-v1 envelope or typed payload is invalid."""


@dataclass(frozen=True)
class ContractSchemas:
    root: Path
    schemas: dict[str, dict[str, Any]]
    validators: dict[str, Any]

    @classmethod
    def load(cls, root: Path | None = None) -> "ContractSchemas":
        contract_root = root or Path(__file__).resolve().parents[2] / "contracts" / "sandbox"
        connector_root = contract_root / "connector" / "v1"
        if not connector_root.is_dir():
            raise FileNotFoundError(f"Missing connector-v1 contracts: {connector_root}")

        schemas: dict[str, dict[str, Any]] = {}
        all_schemas: dict[str, dict[str, Any]] = {}
        for path in sorted(contract_root.glob("*.json")) + [connector_root / filename for filename in SCHEMA_FILES]:
            filename = path.name
            if not path.is_file():
                raise FileNotFoundError(f"Missing connector schema: {path}")
            with path.open(encoding="utf-8") as handle:
                schema = json.load(handle)
            validator_cls = validator_for(schema)
            validator_cls.check_schema(schema)
            all_schemas[filename] = schema
            if path.parent == connector_root:
                schemas[filename] = schema

        store = {schema["$id"]: schema for schema in all_schemas.values() if "$id" in schema}
        validators: dict[str, Any] = {}
        for filename, schema in all_schemas.items():
            validator_cls = validator_for(schema)
            resolver = RefResolver(
                base_uri=path.as_uri(),
                referrer=schema,
                store=store,
            )
            validators[filename] = validator_cls(
                schema,
                resolver=resolver,
                format_checker=FormatChecker(),
            )
        return cls(contract_root, schemas, validators)

    @property
    def version(self) -> str:
        version_path = self.root.parents[1] / "CONTRACTS_VERSION"
        if version_path.is_file():
            return version_path.read_text(encoding="utf-8").strip()
        return "unknown"

    def _validate(self, schema_name: str, value: Any) -> None:
        validator = self.validators.get(schema_name)
        if validator is None:
            raise ProtocolValidationError(f"Unknown connector schema: {schema_name}")
        errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
        if errors:
            first = errors[0]
            location = ".".join(str(part) for part in first.path) or "$"
            raise ProtocolValidationError(f"{schema_name} at {location}: {first.message}")

    def validate_payload(self, kind: str, payload: dict[str, Any]) -> None:
        try:
            schema_name = KIND_TO_SCHEMA[kind]
        except KeyError as exc:
            raise ProtocolValidationError(f"Unsupported connector kind: {kind}") from exc
        self._validate(schema_name, payload)

        if kind == "action":
            verb = payload["verb"]
            if verb not in ALLOWED_VERBS:
                raise ProtocolValidationError(f"Unsupported connector verb: {verb}")
            self._validate(VERB_TO_REQUEST[verb], payload["args"])
        elif kind == "result" and payload.get("status") == "ok" and "result" in payload:
            verb = payload["verb"]
            if verb not in ALLOWED_VERBS:
                raise ProtocolValidationError(f"Unsupported connector verb: {verb}")
            self._validate(VERB_TO_RESPONSE[verb], payload["result"])

    def validate_envelope(self, envelope: dict[str, Any]) -> None:
        self._validate("envelope.schema.json", envelope)
        kind = envelope["kind"]
        self.validate_payload(kind, envelope["payload"])

    def choose_next_action(self, job_envelope: dict[str, Any]) -> dict[str, Any]:
        """Return a fixed safe placeholder; real orchestration is intentionally absent."""
        if job_envelope.get("kind") != "job":
            raise ProtocolValidationError("choose_next_action requires a job envelope")
        self.validate_envelope(job_envelope)
        job_id = job_envelope["payload"]["job_id"]
        action_payload = {
            "job_id": job_id,
            "action_id": str(uuid.uuid4()),
            "verb": "observe_failure",
            "args": {"timeout_seconds": 90},
        }
        action_envelope = {
            "protocol_version": PROTOCOL_VERSION,
            "message_id": str(uuid.uuid4()),
            "job_id": job_id,
            "kind": "action",
            "sent_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "payload": action_payload,
        }
        self.validate_envelope(action_envelope)
        return action_envelope


_SCHEMAS: ContractSchemas | None = None


def get_schemas() -> ContractSchemas:
    global _SCHEMAS
    if _SCHEMAS is None:
        _SCHEMAS = ContractSchemas.load()
    return _SCHEMAS


def validate_envelope(envelope: dict[str, Any]) -> None:
    get_schemas().validate_envelope(envelope)


def choose_next_action(job_envelope: dict[str, Any]) -> dict[str, Any]:
    return get_schemas().choose_next_action(job_envelope)
