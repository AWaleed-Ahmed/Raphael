"""CLI: print operator metrics summary over RunStore."""

from __future__ import annotations

import argparse
import json
import sys

from raphael_agent.metrics import summarize_store
from raphael_agent.store import RunStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Raphael agent RunStore metrics")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON summary",
    )
    args = parser.parse_args(argv)
    summary = summarize_store(RunStore())
    if args.json:
        print(json.dumps(summary, indent=2, default=str))
        return 0
    print(f"generated_at={summary['generated_at']}")
    print(f"runs_total={summary['runs_total']}")
    print(f"by_terminal_status={summary['by_terminal_status']}")
    print(f"ingest_decisions={summary['ingest_decisions']}")
    print(f"publish_modes={summary['publish_modes']}")
    print(f"patch_attempts_total={summary['patch_attempts_total']}")
    print(f"avg_run_duration_seconds={summary['avg_run_duration_seconds']}")
    for note in summary.get("notes") or []:
        print(f"note: {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
