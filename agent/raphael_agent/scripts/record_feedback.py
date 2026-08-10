"""CLI: record human PR outcome into feedback.jsonl (FR-065)."""

from __future__ import annotations

import argparse
import json
import sys

from raphael_agent.feedback import (
    ALLOWED_OUTCOMES,
    JsonlFeedbackRecorder,
    default_feedback_recorder,
    normalize_feedback_event,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record Raphael pilot feedback (accept/reject/merge/…)"
    )
    parser.add_argument(
        "--outcome",
        required=True,
        choices=sorted(ALLOWED_OUTCOMES),
        help="Human / deployment outcome",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--result-id", default=None)
    parser.add_argument("--pr-url", default=None)
    parser.add_argument("--pr-number", type=int, default=None)
    parser.add_argument("--owner", default=None)
    parser.add_argument("--repo", default=None)
    parser.add_argument("--failure-class", default=None)
    parser.add_argument("--actor", default=None)
    parser.add_argument("--notes", default=None)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print recorded event JSON",
    )
    args = parser.parse_args(argv)

    repository = None
    if args.owner and args.repo:
        repository = {"owner": args.owner, "name": args.repo}

    event = normalize_feedback_event(
        {
            "outcome": args.outcome,
            "source": "cli",
            "run_id": args.run_id,
            "result_id": args.result_id,
            "pull_request_url": args.pr_url,
            "pull_request_number": args.pr_number,
            "repository": repository,
            "failure_class": args.failure_class,
            "actor": args.actor,
            "notes": args.notes,
        }
    )
    recorder = default_feedback_recorder()
    recorded = recorder.record(event)
    path = getattr(recorder, "path", None)
    print(f"recorded outcome={recorded['outcome']} event_id={recorded['event_id']}")
    if isinstance(recorder, JsonlFeedbackRecorder):
        print(f"path={recorder.path}")
    elif path:
        print(f"path={path}")
    if args.json:
        print(json.dumps(recorded, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
