"""CLI smoke runner for the Phase 0 stub graph."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from raphael_agent.graph import initial_run_state, run_stub_graph
from raphael_agent.ingest import normalize_failed_run_event
from raphael_agent.sandbox_client import SandboxClient
from raphael_agent.schema_util import validate_agent

AGENT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = AGENT_ROOT.parent
FIXTURE = AGENT_ROOT / "fixtures" / "failed_run_event.json"
DEFAULT_WORKSPACE = (
    REPO_ROOT / "sandbox" / "harness" / "scenarios" / "probe_port_mismatch"
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


def _for_validation(state: dict) -> dict:
    """Remove keys with None values that schemas omit (optional fields)."""
    skip_if_none = {
        "failure_signature",
        "diagnosis",
        "reproduction_result",
        "validated_fix_record",
        "escalation_report",
        "redaction_report",
        "token_and_cost_usage",
        "manifests",
        "workspace_path",
        "target_environment",
        "current_node",
        "pull_request_url",
        "terminal_reason",
        "sandbox_id",
        "result_id",
        "active_patch_id",
        "audit_id",
    }
    out = {}
    for key, value in state.items():
        if key in skip_if_none and value is None:
            continue
        out[key] = value
    repo = dict(out.get("repository") or {})
    if repo.get("clone_url") is None:
        repo.pop("clone_url", None)
    out["repository"] = repo
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Raphael agent Phase 0 smoke path")
    parser.add_argument(
        "--sandbox-mode",
        choices=["auto", "live", "recorded_stub"],
        default="auto",
        help="auto: live if controller /health is up, else recorded stubs",
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

    seed = normalize_failed_run_event(event)
    seed["workspace_path"] = event["workspace_path"]
    seed["manifests"] = event.get("manifests")
    if mode == "live":
        seed["run_id"] = f"asmoke-{uuid.uuid4().hex[:10]}"

    initial = initial_run_state(seed, sandbox_mode=mode)
    final = run_stub_graph(initial)

    validate_agent("run_record.json", _for_validation(final))

    status = final.get("status")
    print(f"sandbox_mode={mode}")
    print(f"run_id={final.get('run_id')}")
    print(f"status={status}")
    print(f"result_id={final.get('result_id')}")
    print(f"terminal_reason={final.get('terminal_reason')}")
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
