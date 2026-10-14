"""Opt-in synthetic connectivity smoke, never a diagnosis/repair proof."""
from __future__ import annotations

import argparse

from raphael_agent.byok.client import BYOKError, complete_json
from raphael_agent.byok.models import BYOKConfig


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly send one synthetic provider request")
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required")
    try:
        config = BYOKConfig.from_env()
        if config is None:
            raise ValueError("llm_key_not_configured")
        result = complete_json(config, system='Return only the JSON object {"ok": true}.', payload={"synthetic": True})
        if result.parsed_json != {"ok": True}:
            raise BYOKError("unexpected_smoke_response")
        print(f"PASS synthetic connectivity: provider={config.provider.value} model={result.model}")
        return 0
    except (ValueError, BYOKError) as exc:
        print(f"FAIL synthetic connectivity: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
