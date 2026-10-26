"""Measure real artifacts at production graph call sites using public fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import statistics
import subprocess
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import perf_counter
from typing import Any, Self

from raphael_agent.graph import build_stub_graph, initial_run_state, nodes
from raphael_agent.local_inference import artifacts
from raphael_agent.model_gateway import ModelGateway
from raphael_agent.schema_util import for_run_record_validation, validate_agent

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "agent/tests/fixtures/local_inference"
OWNER = {
    "tenant_id": "fixture-tenant-a",
    "company_id": "fixture-company-a",
    "client_id": "fixture-client-a1",
}
REPOSITORY = {"owner": "proof-source", "name": "raphael-e2e-fixture"}


class Catalog:
    """Real loopback REST transport for explicitly labelled catalog fixtures."""

    def __init__(self) -> None:
        self.baselines: list[dict[str, Any]] = []
        self.requests = 0
        catalog = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                pass

            def do_GET(self) -> None:
                catalog.requests += 1
                rows = (
                    [{**OWNER, "status": "active", "client_name": "public-fixture"}]
                    if "/raphael_clients?" in self.path
                    else catalog.baselines
                )
                body = json.dumps(rows).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:
                self.send_response(201)
                self.end_headers()
                self.wfile.write(b"[]")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> Self:
        self.thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"


@contextmanager
def configured(catalog: Catalog, model_root: Path, data_root: Path) -> Iterator[None]:
    """Bind only fictional fixture scope and disable publication/external models."""
    settings = {
        "RAPHAEL_MODEL_ENABLED": "1",
        "RAPHAEL_MODEL_ROOT": str(model_root),
        "RAPHAEL_AGENT_TENANT_ID": OWNER["tenant_id"],
        "RAPHAEL_COMPANY_ID": OWNER["company_id"],
        "RAPHAEL_CLIENT_ID": OWNER["client_id"],
        "RAPHAEL_HEALTHY_CATALOG_ENABLED": "1",
        "SUPABASE_URL": catalog.url,
        "SUPABASE_SERVICE_ROLE_KEY": "fixture-only-key",
        "RAPHAEL_PARTNER_MODE": "dry_run",
        "RAPHAEL_PUBLISH_MODE": "dry_run",
        "RAPHAEL_LLM_DIAGNOSIS": "0",
        "RAPHAEL_LLM_PATCH": "0",
        "RAPHAEL_LEARNING": "0",
        "RAPHAEL_AGENT_DATA_DIR": str(data_root),
        "RAPHAEL_DIAGNOSIS_CONFIDENCE_THRESHOLD": "0.7",
        "GITHUB_TOKEN": "",
        "RAPHAEL_GITHUB_TOKEN": "",
        "RAPHAEL_GITHUB_APP_ID": "",
        "RAPHAEL_GITHUB_APP_PRIVATE_KEY": "",
        "RAPHAEL_GITHUB_APP_PRIVATE_KEY_PATH": "",
    }
    previous = {key: os.environ.get(key) for key in settings}
    os.environ.update(settings)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def state_for(case: dict[str, Any], index: int = 0) -> dict[str, Any]:
    """Project public evidence through the normal run boundary and collector."""
    payload, source = case["input"], case["source"]
    state = dict(
        initial_run_state(
            {
                **OWNER,
                "run_id": f"model-proof-{index}",
                "trigger": {"kind": "github_issue"},
                "repository": REPOSITORY,
                "commit_sha": "a" * 40,
                "target_environment": "fixture-replay",
                "issue_title": source.get("title", source["dataset"]),
                "issue_body": payload.get("evidence_text")
                or source.get("body_excerpt", ""),
                "runtime_observation": {
                    **payload,
                    "service_name": "public-fixture",
                    "operation": "request",
                    "environment": "fixture-replay",
                },
            },
            sandbox_mode="recorded_stub",
        )
    )
    state.update(
        status="running",
        failure_signature={
            "key": payload.get("fingerprint", "public-fixture"),
            "class": payload.get("failure_class", "generic_failure"),
            "normalized": {"reason": payload.get("normalized_reason", "")},
        },
        failure_fingerprint=payload.get("fingerprint"),
    )
    state.update(nodes.node_evidence(state))
    return state


def baseline_for(state: dict[str, Any], latency: float) -> dict[str, Any]:
    """Adapt RCAEval healthy-window measurements; ownership is a test assignment."""
    observation = state["runtime_observation"]
    return {
        **OWNER,
        "healthy_trace_id": "public-window-baseline",
        "verified_healthy": True,
        "service_name": observation["service_name"],
        "environment": observation["environment"],
        "operation": observation["operation"],
        "repository": "/".join(REPOSITORY.values()),
        "latency_ms": latency,
        "error_span_count": 0,
        "status_code": 200,
        "span_sequence": [],
    }


def canonical(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adapt existing benchmark candidates without inventing new source records."""
    methods = {
        "stack_trace_match": "stack_trace",
        "changed_file_match": "deployment_diff",
        "trace_divergence_match": "trace_divergence",
        "log_callsite_match": "log_template",
        "route_handler_match": "route_to_handler",
    }
    return [
        {
            "repository": "/".join(REPOSITORY.values()),
            "git_sha": "a" * 40,
            "path": row["candidate_path"],
            "line": row.get("candidate_line", 0),
            "symbol": row.get("candidate_symbol", ""),
            "candidate_type": row["candidate_type"],
            "score": row.get("runtime_anchor_score", 0),
            "evidence_refs": [],
            "mapping_methods": [
                method for key, method in methods.items() if row.get(key)
            ],
            "state": "suspected",
            "diff_hunk": None,
        }
        for row in rows
    ]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep coverage, decision source and quality denominators explicit."""
    outputs = [row["output"] for row in rows if row["output"] is not None]
    times = sorted(row["elapsed_ms"] for row in rows)
    return {
        "cases": len(rows),
        "available": len(outputs),
        "learned_execution": sum(bool(row.get("learned_execution")) for row in outputs),
        "rule_overrides": sum(bool(row.get("rule_based")) for row in outputs),
        "abstentions": sum(
            row.get("execution_source") == "abstention" for row in outputs
        ),
        "label_matches": sum(row["label_match"] is True for row in rows),
        "label_denominator": sum(row["label_match"] is not None for row in rows),
        "available_label_denominator": sum(
            row["output"] is not None and row["label_match"] is not None for row in rows
        ),
        "unavailable_reasons": {
            reason: sum(
                row.get("unavailable_reason") == reason and row["output"] is None
                for row in rows
            )
            for reason in sorted(
                {
                    str(row.get("unavailable_reason"))
                    for row in rows
                    if row["output"] is None
                }
            )
        },
        "median_ms": round(statistics.median(times), 3),
        "p95_ms": round(times[max(0, math.ceil(len(times) * 0.95) - 1)], 3),
    }


def qualify(model_root: Path, cases_root: Path, output: Path) -> dict[str, Any]:
    """Execute graph nodes and a compiled graph with real loaded estimators."""
    output.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "libraries": artifacts.RUNTIME_VERSIONS,
        "models": {},
    }
    report["source_sha256"] = {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in (
            "agent/raphael_agent/model_gateway.py",
            "agent/raphael_agent/model_outputs.py",
            "agent/raphael_agent/graph/nodes.py",
            "agent/scripts/qualify_model_graph.py",
        )
    }
    try:
        report["revision"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except subprocess.SubprocessError:
        report["revision"] = "unavailable"
    with (
        tempfile.TemporaryDirectory(prefix="graph-proof-") as temporary,
        Catalog() as catalog,
        configured(catalog, model_root, Path(temporary)),
    ):
        for name in (
            "failure_classifier",
            "candidate_ranker",
            "incident_similarity",
            "trace_anomaly",
            "patch_selector",
        ):
            cases_path = cases_root / f"{name}.jsonl"
            cases = [json.loads(line) for line in cases_path.read_text().splitlines()]
            artifacts._load_bundle.cache_clear()
            start = perf_counter()
            artifacts.load_bundle(model_root, name)
            cold = (perf_counter() - start) * 1000
            rows = []
            for index, case in enumerate(cases):
                catalog.baselines = []
                state = state_for(case, index)
                expected = case["expected"]
                start = perf_counter()
                layer = "production_graph_node"
                if name == "failure_classifier":
                    updates = nodes.node_diagnose(state)
                    result = (updates.get("model_results") or {}).get(name)
                    label = (result or {}).get("failure_class") == expected[
                        "failure_class"
                    ]
                elif name == "candidate_ranker":
                    # Candidate fixtures were generated by a historical benchmark,
                    # not captured production stacks. Measure the production adapter
                    # separately; graph generation is exercised in compiled proof.
                    layer = "production_gateway_projection"
                    before = canonical(case["input"]["candidates"])
                    ranked = ModelGateway().rank_candidates(state, before, [])
                    result = ranked["model"] if ranked else None
                    updates = {}
                    label = (
                        ranked is not None
                        and ranked["candidates"][0]["path"]
                        in expected["patched_source_files"]
                    )
                    if ranked:
                        identity = lambda row: (
                            row["path"],
                            row["line"],
                            row["symbol"],
                            row["evidence_refs"],
                            row["mapping_methods"],
                        )
                        assert sorted(map(repr, map(identity, before))) == sorted(
                            map(repr, map(identity, ranked["candidates"]))
                        )
                elif name == "incident_similarity":
                    updates = nodes.node_localize(state)
                    result = updates["model_results"].get(name)
                    hits = (result or {}).get("results") or []
                    label = (
                        bool(hits)
                        and hits[0]["failure_class"] == expected["failure_class"]
                    )
                    assert all(
                        all(row.get(k) == v for k, v in OWNER.items()) for row in hits
                    )
                elif name == "trace_anomaly":
                    latency = case["input"].get("baseline_latency_ms")
                    catalog.baselines = (
                        [baseline_for(state, latency)] if latency else []
                    )
                    updates = nodes.node_localize(state)
                    result = updates["model_results"].get(name)
                    label = (result or {}).get("is_anomaly") == expected["is_anomaly"]
                else:
                    state.update(
                        reproduction_result={"reproduced": True},
                        diagnosis={
                            "classification": {
                                "category": "supported",
                                "failure_class": case["input"]["failure_class"],
                            }
                        },
                        fault_candidates=[
                            {
                                "candidate_type": case["input"]["candidate_type"],
                                "symbol": case["input"]["manifest_field"],
                                "path": "deploy/manifests/app.yaml",
                            }
                        ],
                    )
                    updates = nodes.node_patch(state)
                    result = updates.get("model_results", {}).get(name)
                    label = (
                        None
                        if "learned_execution" in expected
                        else (
                            bool((result or {}).get("policy_allowed"))
                            and (result or {}).get("safe_template")
                            in expected["acceptable_templates"]
                        )
                    )
                elapsed = (perf_counter() - start) * 1000
                unavailable = (updates.get("model_results") or {}).get(name) or {}
                reason = (
                    unavailable.get("reason")
                    if unavailable.get("available") is False
                    else updates.get("terminal_reason")
                )
                if result and result.get("available") is False:
                    result = None
                row = {
                    "capability": name,
                    "case": index,
                    "source": case["source"],
                    "input": case["input"],
                    "output": result,
                    "layer": layer,
                    "label_match": bool(label) if label is not None else None,
                    "unavailable_reason": reason,
                    "graph_status": updates.get("status"),
                    "terminal_reason": updates.get("terminal_reason"),
                    "elapsed_ms": round(elapsed, 3),
                    "audit": [
                        event
                        for event in updates.get("audit_events", [])
                        if event["event"] == "model_execution"
                    ],
                }
                rows.append(row)
                records.append(row)
            report["models"][name] = {
                **summarize(rows),
                "cold_load_ms": round(cold, 3),
                "fixture_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
                "artifact_sha256": artifacts.TRUSTED_ARTIFACTS[name][1],
            }
        # Actual compiled production graph: controlled manifest fixture,
        # recorded sandbox responses, real local models and REST catalog.
        workspace = ROOT / "agent/fixtures/scenarios/probe_port_mismatch"
        seed = {
            **OWNER,
            "run_id": "compiled-real-model-proof",
            "trigger": {"kind": "fixture"},
            "repository": REPOSITORY,
            "commit_sha": "a" * 40,
            "workspace_path": str(workspace),
            "manifests": {"type": "yaml", "path": "deploy/manifests"},
            "target_environment": "fixture-replay",
            "runtime_observation": {
                "service_name": "public-fixture",
                "operation": "request",
                "environment": "fixture-replay",
            },
        }
        compiled_state = initial_run_state(seed, sandbox_mode="recorded_stub")
        catalog.baselines = [baseline_for(dict(compiled_state), 10)]
        start = perf_counter()
        graph_builder: Any = build_stub_graph
        final = graph_builder().invoke(compiled_state)
        elapsed = (perf_counter() - start) * 1000
        validate_agent("run_record.json", for_run_record_validation(final))
        assert final["status"] == "success_draft_pr_ready", final.get("terminal_reason")
        assert set(final["model_results"]) >= set(report["models"])
        assert all(
            final["model_results"][name].get("available") is not False
            for name in report["models"]
        )
        report["compiled_graph"] = {
            "status": final["status"],
            "elapsed_ms": round(elapsed, 3),
            "sandbox": "recorded responses, not a live repair",
            "model_results": final["model_results"],
            "catalog_http_requests": catalog.requests,
        }
        (output / "compiled-run.json").write_text(
            json.dumps(for_run_record_validation(final), indent=2, sort_keys=True)
            + "\n"
        )
    report["peak_process_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    (output / "cases.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in records)
    )
    (output / "summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, default=ROOT / "models")
    parser.add_argument("--cases-root", type=Path, default=CASES)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = qualify(
        args.model_root.resolve(), args.cases_root.resolve(), args.output.resolve()
    )
    print(json.dumps({name: data for name, data in report["models"].items()}, indent=2))


if __name__ == "__main__":
    main()
