"""Keep lease credentials out of persisted E2E evidence."""
from __future__ import annotations

import json
from typing import Any


def redacted_body(body: bytes) -> str:
    if not body:
        return ""
    try:
        value = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return "[non-JSON body omitted]"

    def scrub(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: "[redacted]" if key in {"claim_id", "connector_id"} else scrub(value)
                    for key, value in item.items()}
        if isinstance(item, list):
            return [scrub(value) for value in item]
        return item

    return json.dumps(scrub(value))
