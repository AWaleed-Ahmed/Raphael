"""Explicit operational fault controls over original inputs, never accuracy cases."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import os
import shutil
import socket
import tempfile
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest.mock import patch

_runtime = importlib.import_module(
    f"{__package__}.qualify_model_runtime" if __package__ else "qualify_model_runtime"
)
configure = _runtime.configure
digest = _runtime.digest


def controls(cases: list[dict[str, Any]], model_root: Path) -> list[dict[str, Any]]:
    """Verify real fallback/guards; patched failures are labelled operational controls."""
    joblib = importlib.import_module("joblib")
    from raphael_agent.local_inference import artifacts, predict
    from raphael_agent.model_gateway import ModelGateway, model_error

    InconsistentVersionWarning = importlib.import_module(
        "sklearn.exceptions"
    ).InconsistentVersionWarning

    records: list[dict[str, Any]] = []
    for case in cases:
        state = case["state"]
        before = digest(state)
        for damage in (
            "missing_artifact",
            "corrupt_artifact",
            "missing_manifest",
            "corrupt_manifest",
            "forged_manifest_pair",
        ):
            with tempfile.TemporaryDirectory(prefix="model-fault-") as directory:
                root = Path(directory)
                shutil.copytree(
                    model_root / "failure_classifier", root / "failure_classifier"
                )
                artifacts._load_bundle.cache_clear()
                assert ModelGateway(root).classify_failure(state) is not None
                target = root / "failure_classifier"
                if damage == "missing_artifact":
                    (target / "model.joblib").unlink()
                elif damage == "missing_manifest":
                    (target / "manifest.json").unlink()
                elif damage == "corrupt_manifest":
                    (target / "manifest.json").write_text("{}")
                else:
                    (target / "model.joblib").write_bytes(
                        b"disposable-corruption-control"
                    )
                    if damage == "forged_manifest_pair":
                        manifest = json.loads((target / "manifest.json").read_text())
                        manifest["artifact_sha256"] = hashlib.sha256(
                            (target / "model.joblib").read_bytes()
                        ).hexdigest()
                        (target / "manifest.json").write_text(json.dumps(manifest))
                cached = ModelGateway(root).classify_failure(state)
                assert (
                    cached is not None
                )  # Immutable verified cached bytes remain valid.
                artifacts._load_bundle.cache_clear()
                with patch.object(joblib, "load", wraps=joblib.load) as deserialize:
                    gateway = ModelGateway(root)
                    result = gateway.classify_failure(state)
                    assert result is None and deserialize.call_count == 0
                reason = model_error(gateway)
                shutil.rmtree(target)
                shutil.copytree(model_root / "failure_classifier", target)
                recovered = ModelGateway(root).classify_failure(state)
                assert recovered is not None
                records.append(
                    {
                        "case_id": case["id"],
                        "control": damage,
                        "cold_available": False,
                        "reason": reason,
                        "deserializer_calls_for_invalid_bytes": 0,
                        "warm_verified_object_remained_available": True,
                        "restored_available": True,
                    }
                )
        for control in (
            "dependency_version",
            "estimator_warning",
            "runtime_exception",
            "malformed",
            "nonfinite",
            "unknown_class",
        ):
            artifacts._load_bundle.cache_clear()
            if control == "dependency_version":
                injected = patch.object(
                    artifacts, "version", return_value="unqualified"
                )
                expected = "incompatible_runtime_dependencies"
            elif control == "estimator_warning":

                def warn(*args: Any, **kwargs: Any) -> None:
                    warnings.warn(
                        InconsistentVersionWarning(
                            estimator_name="operational_control",
                            current_sklearn_version="1.9.0",
                            original_sklearn_version="unqualified",
                        ),
                        stacklevel=1,
                    )

                injected = patch.object(joblib, "load", side_effect=warn)
                expected = "artifact_deserialization_failed"
            elif control == "runtime_exception":
                injected = patch.object(
                    predict,
                    "classify_failure",
                    side_effect=RuntimeError("PRIVATE_CONTROL_TEXT"),
                )
                expected = "RuntimeError"
            else:
                output: Any = (
                    []
                    if control == "malformed"
                    else {
                        "abstained": False,
                        "confidence": float("nan") if control == "nonfinite" else 0.99,
                        "failure_class": "unregistered_private_class",
                    }
                )
                injected = patch.object(
                    predict, "classify_failure", return_value=output
                )
                expected = "invalid_model_output"
            with injected:
                gateway = ModelGateway(model_root)
                assert gateway.classify_failure(state) is None
                assert model_error(gateway) == expected
            records.append(
                {
                    "case_id": case["id"],
                    "control": control,
                    "reason": expected,
                    "available": False,
                    "kind": "injected_operational_control_not_a_positive_model_prediction",
                }
            )
        assert digest(state) == before
    # Every registered family rejects changed bytes before deserialization.
    for name in artifacts.TRUSTED_ARTIFACTS:
        with tempfile.TemporaryDirectory(prefix="registry-fault-") as directory:
            root = Path(directory)
            shutil.copytree(model_root / name, root / name)
            (root / name / "model.joblib").write_bytes(b"disposable-corruption-control")
            artifacts._load_bundle.cache_clear()
            with patch.object(joblib, "load", wraps=joblib.load) as deserialize:
                try:
                    artifacts.load_bundle(root, name)
                except artifacts.ArtifactUnavailable as exc:
                    assert str(exc) == "artifact_hash_mismatch"
                else:
                    raise AssertionError("corrupt_artifact_accepted")
                assert deserialize.call_count == 0
            records.append(
                {
                    "model": name,
                    "control": "registry_family_corruption",
                    "deserializer_calls_for_invalid_bytes": 0,
                    "available": False,
                }
            )
    return records


def isolation(cases: list[dict[str, Any]], root: Path) -> list[dict[str, Any]]:
    """Use request-local gateways while alternating valid and forged identities."""
    from raphael_agent.model_gateway import ModelGateway, model_error

    def check(job: tuple[dict[str, Any], str | None]) -> dict[str, Any]:
        case, field = job
        state = copy.deepcopy(case["state"])
        if field:
            state[field] = "wrong-owner-control"
        gateway = ModelGateway(root)
        result = gateway.similar_incidents(state)
        if field:
            assert result is None and model_error(gateway) == "incident_scope_mismatch"
        else:
            assert result is not None and model_error(gateway) is None
            assert all(
                row["tenant_id"] == "fixture-tenant-a"
                and row["company_id"] == "fixture-company-a"
                and row["client_id"] == "fixture-client-a1"
                for row in result["results"]
            )
        return {
            "case_id": case["id"],
            "field": field,
            "reason": model_error(gateway),
            "ownership_violation": False,
        }

    tasks = [
        (case, field)
        for case in cases
        for field in (None, "tenant_id", "company_id", "client_id")
        for _ in range(8)
    ]
    serial = [check(task) for task in tasks]
    with ThreadPoolExecutor(max_workers=4) as pool:
        parallel = list(pool.map(check, tasks))
    assert serial == parallel
    return parallel


def graph_guards(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Use original reports with actual production nodes and a real network outage."""
    from raphael_agent.graph import initial_run_state, nodes

    records = []
    for case in cases:
        state: dict[str, Any] = dict(
            initial_run_state({**case["state"], "run_id": "fault-graph-" + case["id"]})
        )
        state["issue_body"] = case["state"].get("issue_body", "")
        state.update(nodes.node_evidence(state))
        state.update(nodes.node_diagnose(state))
        state.update(nodes.node_patch(state))
        assert not state.get("candidate_patches")
        records.append(
            {
                "case_id": case["id"],
                "control": "real_report_graph_preconditions",
                "classification": (state.get("diagnosis") or {}).get("classification"),
                "status": state["status"],
                "reason": state.get("terminal_reason"),
                "patch_proposals": 0,
            }
        )
        # Reserve a real local port without listening; a real HTTP connection fails.
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            os.environ.update(
                RAPHAEL_HEALTHY_CATALOG_ENABLED="1",
                SUPABASE_URL=f"http://127.0.0.1:{reserved.getsockname()[1]}",
                SUPABASE_SERVICE_ROLE_KEY="operational-control-only",
            )
            isolated = dict(
                initial_run_state({**case["state"], "run_id": "network-" + case["id"]})
            )
            update: dict[str, Any] = dict(nodes.node_localize(isolated))
            assert not update.get("healthy_trace_comparisons")
            assert not update.get("fault_candidates")
            assert update["localization_result"]["status"] == "error"
            assert update["localization_result"]["reason"] == "localization_failed"
            records.append(
                {
                    "case_id": case["id"],
                    "control": "real_catalog_connection_refused",
                    "localization_result": update["localization_result"],
                    "healthy_baselines_fabricated": 0,
                }
            )
    return records


def concurrent_faults(cases: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    """Malformed output under admitted concurrency cannot survive validators."""
    from raphael_agent.local_inference import predict
    from raphael_agent.model_gateway import ModelGateway, model_error

    def reject(case: dict[str, Any]) -> dict[str, Any]:
        gateway = ModelGateway(root)
        assert gateway.classify_failure(case["state"]) is None
        assert model_error(gateway) == "invalid_model_output"
        return {"case_id": case["id"], "reason": model_error(gateway)}

    with patch.object(
        predict,
        "classify_failure",
        return_value={
            "abstained": False,
            "confidence": float("nan"),
            "failure_class": "healthy",
        },
    ), ThreadPoolExecutor(max_workers=4) as pool:
        denied = list(pool.map(reject, cases * 8))
    # No request-local failure may poison a later real prediction.
    recovered = [
        ModelGateway(root).classify_failure(case["state"]) is not None for case in cases
    ]
    assert all(recovered)
    return {
        "control": "nonfinite_outputs_at_concurrency_4",
        "denied": denied,
        "subsequent_real_predictions_available": recovered,
    }


def main() -> None:
    """Write only bounded outcomes, excluding original report/log content."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    configure(True)
    bundle = json.loads(args.cases.read_text())
    result = {
        "kind": "operational_controls_not_accuracy",
        "input_bundle_sha256": digest(bundle),
        "faults": controls(bundle["faults"], args.model_root),
        "isolation": isolation(bundle["safety"], args.model_root),
        "concurrent_failures": concurrent_faults(bundle["faults"], args.model_root),
        "graph_guards": graph_guards(bundle["safety"]),
    }
    encoded = json.dumps(result, sort_keys=True, indent=2)
    assert (
        "PRIVATE_CONTROL_TEXT" not in encoded
        and "unregistered_private_class" not in encoded
    )
    with args.output.open("x") as target:
        target.write(encoded + "\n")
    print("fault, isolation and original-report graph controls passed")


if __name__ == "__main__":
    main()
