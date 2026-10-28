"""Read-only local inference over one frozen, operator-owned run snapshot.

The CLI runs separately with ceilings of 30 CPU seconds and 512 MiB of address
space. It never imports the orchestrator, writes RunStore, or invokes sandbox
or publication actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .incident_scope import scope_for_run
from .model_gateway import ModelGateway, model_mode
from .model_outputs import execution_source
from .timeutil import utc_now


def evaluate_snapshot(snapshot: dict[str, Any], model_root: Path | None = None) -> dict[str, Any]:
    """Produce counterfactuals without merging any prediction into the snapshot."""
    if model_mode() != "shadow":
        raise ValueError("shadow_mode_required")
    scope_for_run(snapshot)
    frozen = json.dumps(snapshot, sort_keys=True, allow_nan=False).encode()
    gateway = ModelGateway(model_root, observer=True)
    results = {}
    blocked = ((snapshot.get("diagnosis") or {}).get("classification") or {}).get("category") == "blocked"
    for capability, call in (
        ("failure_classifier", lambda: gateway.classify_failure(snapshot)),
        ("incident_similarity", lambda: gateway.similar_incidents(snapshot)),
        ("trace_anomaly", lambda: gateway.trace_anomaly(snapshot)),
        ("candidate_ranker", lambda: gateway.rank_candidates(snapshot, snapshot.get("fault_candidates") or [], snapshot.get("healthy_trace_comparisons") or [])),
        ("patch_selector", lambda: gateway.select_patch(snapshot)),
    ):
        if blocked and capability in {"failure_classifier", "patch_selector"}:
            results[capability] = {"suggestion": None, "audit": {
                "capability": capability, "source": "not_applicable", "attempted": False,
                "reason": "policy_blocked",
            }}
            continue
        result = call()
        results[capability] = {
            "suggestion": result,
            "audit": gateway.audit_metadata() or {"source": execution_source(result)},
        }
    return {
        "recorded_at": utc_now(), "run_id": snapshot.get("run_id"),
        "result_id": snapshot.get("result_id"), "gate_version": "1",
        "snapshot_sha256": hashlib.sha256(frozen).hexdigest(),
        "observer_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "gateway_code_sha256": hashlib.sha256(Path(__file__).with_name("model_gateway.py").read_bytes()).hexdigest(),
        "evidence_tier": "shadow_counterfactual", "repair_outcome": "unmeasured",
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    # Only inference configuration is needed. Never pass integration credentials
    # into this observer's execution environment.
    permitted = {
        "RAPHAEL_MODEL_ENABLED", "RAPHAEL_MODEL_MODE", "RAPHAEL_MODEL_CAPABILITIES",
        "RAPHAEL_MODEL_STOP_FILE", "RAPHAEL_MODEL_ROOT", "RAPHAEL_AGENT_TENANT_ID",
        "RAPHAEL_COMPANY_ID", "RAPHAEL_CLIENT_ID",
    }
    settings = {key: value for key, value in os.environ.items() if key in permitted}
    os.environ.clear()
    os.environ.update(settings, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        with args.snapshot.open("rb") as source:
            raw = source.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("snapshot_too_large")
        result = evaluate_snapshot(json.loads(raw))
        # Exclusive creation avoids overwriting evidence or following a symlink.
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as output:
            json.dump(result, output, sort_keys=True, allow_nan=False)
            output.write("\n")
    except (OSError, ValueError, TypeError):
        parser.exit(1, "shadow_evaluation_failed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
