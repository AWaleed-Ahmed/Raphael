"""Day 0–1 local pilot proofs (no design partner required)."""

from __future__ import annotations

import os
import subprocess
import sys


def _run(cmd: list[str]) -> int:
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(cmd)


def main() -> int:
    os.environ.setdefault("RAPHAEL_PARTNER_MODE", "dry_run")
    os.environ.setdefault("RAPHAEL_LLM_DIAGNOSIS", "0")
    os.environ.setdefault("RAPHAEL_LLM_PATCH", "0")
    os.environ.setdefault("RAPHAEL_PUBLISH_MODE", "dry_run")

    steps = [
        [sys.executable, "-m", "raphael_agent.scripts.pilot_go_nogo"],
        [sys.executable, "-m", "raphael_agent.scripts.demo_partner"],
        [sys.executable, "-m", "pytest", "-q"],
        [sys.executable, "-m", "raphael_agent.scripts.metrics"],
    ]
    for cmd in steps:
        code = _run(cmd)
        if code != 0:
            print(f"preflight FAILED at: {' '.join(cmd)}", flush=True)
            return code
    print(
        "preflight OK - local Day 0-1 proofs passed. "
        "Real partner week (secrets, >=5 failures, approval) still required for PRD Phase 5 exit.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
