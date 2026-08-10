"""CLI: pilot go / no-go checks from current environment."""

from __future__ import annotations

import argparse
import json
import sys

from raphael_agent.guardrails import go_nogo_verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Raphael pilot go/no-go env check")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    verdict = go_nogo_verdict()
    if args.json:
        print(json.dumps(verdict, indent=2))
    else:
        print(f"go={verdict['go']}")
        print(f"recommendation={verdict['recommendation']}")
        for item in verdict["checks"]:
            mark = "OK" if item["ok"] else "FAIL"
            print(f"  [{mark}] {item['id']}: {item['detail']}")
        if verdict["failed"]:
            print(f"failed={verdict['failed']}")
    return 0 if verdict["go"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
