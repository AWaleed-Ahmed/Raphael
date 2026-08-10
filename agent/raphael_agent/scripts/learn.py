"""Rebuild offline learning_snapshot from FR-065 feedback."""

from __future__ import annotations

import argparse
import json

from raphael_agent.learning import (
    build_learning_snapshot,
    save_learning_snapshot,
    snapshot_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build learning_snapshot.json from feedback.jsonl (offline)."
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=None,
        help="Override RAPHAEL_LEARNING_MIN_SAMPLES",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path (default RAPHAEL_LEARNING_SNAPSHOT / data dir)",
    )
    args = parser.parse_args()
    snapshot = build_learning_snapshot(min_n=args.min_samples)
    from pathlib import Path

    path = save_learning_snapshot(
        snapshot, Path(args.out) if args.out else snapshot_path()
    )
    print(f"snapshot_id={snapshot['snapshot_id']}")
    print(f"classes={len(snapshot['classes'])}")
    print(f"path={path}")
    print(json.dumps({"classes": snapshot["classes"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
