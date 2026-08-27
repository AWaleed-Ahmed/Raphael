"""CLI smoke runner for the agent graph (+ Phase 1 ingest path)."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from raphael_agent.graph import initial_run_state, run_stub_graph
from raphael_agent.ingest import accept_and_run_graph, normalize_failed_run_event
from raphael_agent.sandbox_client import SandboxClient
from raphael_agent.schema_util import for_run_record_validation, validate_agent
from raphael_agent.store import RunStore

AGENT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = AGENT_ROOT.parent
FIXTURE = AGENT_ROOT / "fixtures" / "failed_run_event.json"
DEFAULT_WORKSPACE = (
    REPO_ROOT / "agent" / "fixtures" / "scenarios" / "probe_port_mismatch"
)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def choose_sandbox_mode(force: str | None) -> str:
    if force in {"live", "recorded_stub"}:
        return force
    client = SandboxClient(validate=False)
    if client.is_reachable():
        return "live"
    return "recorded_stub"


# Back-compat for tests importing _for_validation
def _for_validation(state: dict) -> dict:
    return for_run_record_validation(state)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Raphael agent smoke path")
    parser.add_argument(
        "--sandbox-mode",
        choices=["auto", "live", "recorded_stub"],
        default="auto",
        help="auto: live if controller /health is up, else recorded stubs",
    )
    parser.add_argument(
        "--via-ingest",
        action="store_true",
        help="Route through Phase 1 accept_and_run_graph (persist + policy)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print final run_record JSON",
    )
    args = parser.parse_args(argv)

    force = None if args.sandbox_mode == "auto" else args.sandbox_mode
    mode = choose_sandbox_mode(force)

    event = load_fixture()
    if not event.get("workspace_path"):
        event["workspace_path"] = str(DEFAULT_WORKSPACE)

    if mode == "live":
        event["run_id"] = f"asmoke-{uuid.uuid4().hex[:10]}"

    if args.via_ingest:
        store = RunStore()
        decision, final = accept_and_run_graph(
            event, store=store, sandbox_mode=mode
        )
        print(f"ingest_decision={decision.get('decision')}")
        if final is None:
            print(f"ingest suppressed: {decision.get('reason')}")
            return 0 if decision.get("decision") in {
                "duplicate",
                "cooldown",
                "concurrency_limit",
                "ignored",
            } else 5
    else:
        seed = normalize_failed_run_event(event)
        seed["workspace_path"] = event["workspace_path"]
        seed["manifests"] = event.get("manifests")
        if mode == "live":
            seed["run_id"] = event["run_id"]
        initial = initial_run_state(seed, sandbox_mode=mode)
        final = run_stub_graph(initial)

    assert final is not None
    validate_agent("run_record.json", for_run_record_validation(final))

    status = final.get("status")
    print(f"sandbox_mode={mode}")
    print(f"run_id={final.get('run_id')}")
    print(f"status={status}")
    print(f"result_id={final.get('result_id')}")
    print(f"pull_request_url={final.get('pull_request_url')}")
    pub = final.get("publish") or {}
    if pub:
        print(
            f"publish_mode={pub.get('mode')} dry_run={pub.get('dry_run')} "
            f"draft={pub.get('draft')}"
        )
    print(f"terminal_reason={final.get('terminal_reason')}")
    if final.get("failure_fingerprint"):
        print(f"fingerprint={final.get('failure_fingerprint')}")
    if final.get("budget_snapshot"):
        snap = final["budget_snapshot"]
        print(
            f"budget_wall_s={snap.get('max_wall_seconds')} "
            f"deadline_at={snap.get('deadline_at')}"
        )
    if final.get("errors"):
        print(f"errors={final.get('errors')}")
    if args.json:
        print(json.dumps(final, indent=2, default=str))

    if status not in {"success_draft_pr_ready", "escalated", "failed_closed"}:
        print("unexpected non-terminal status", file=sys.stderr)
        return 2
    if mode == "recorded_stub" and status != "success_draft_pr_ready":
        print("recorded stub path did not succeed", file=sys.stderr)
        return 3
    if mode == "live" and status != "success_draft_pr_ready":
        print("live sandbox path did not succeed", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
