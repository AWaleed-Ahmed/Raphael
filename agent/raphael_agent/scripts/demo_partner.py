"""Canonical partner dry-run demo wrapper (Phase 5)."""

from __future__ import annotations

import os
import sys


def main(argv: list[str] | None = None) -> int:
    """Force partner-safe env defaults, then run recorded_stub smoke."""
    os.environ.setdefault("RAPHAEL_PARTNER_MODE", "dry_run")
    os.environ.setdefault("RAPHAEL_PUBLISH_MODE", "dry_run")
    os.environ.setdefault("RAPHAEL_LLM_DIAGNOSIS", "0")
    # Empty allowlist — live impossible even if someone sets PUBLISH_MODE=live mid-demo
    os.environ.setdefault("RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES", "")

    from raphael_agent.scripts.smoke import main as smoke_main

    args = list(argv) if argv is not None else []
    if "--sandbox-mode" not in args:
        args = ["--sandbox-mode", "recorded_stub", *args]
    print("demo_partner: RAPHAEL_PARTNER_MODE=%s" % os.environ.get("RAPHAEL_PARTNER_MODE"))
    print("demo_partner: RAPHAEL_PUBLISH_MODE=%s" % os.environ.get("RAPHAEL_PUBLISH_MODE"))
    return smoke_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
