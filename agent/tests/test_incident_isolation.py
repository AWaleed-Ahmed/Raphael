"""Tenant isolation through the real packaged incident-similarity path."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from raphael_agent.incident_scope import IncidentScope
from raphael_agent.local_inference import artifacts, predict
from raphael_agent.model_gateway import ModelGateway, model_error

ROOT = Path(__file__).resolve().parents[2]


def test_scope_less_retrieval_refuses(monkeypatch):
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")
    for key in ("RAPHAEL_AGENT_TENANT_ID", "RAPHAEL_COMPANY_ID", "RAPHAEL_CLIENT_ID"):
        monkeypatch.delenv(key, raising=False)
    gateway = ModelGateway(ROOT / "models")
    assert gateway.similar_incidents({"tenant_id": "forged"}) is None
    assert model_error(gateway) == "incident_scope_unverified"


SCOPE_KEYS = ("RAPHAEL_AGENT_TENANT_ID", "RAPHAEL_COMPANY_ID", "RAPHAEL_CLIENT_ID")
SCOPES = (
    IncidentScope("fixture-tenant-a", "fixture-company-a", "fixture-client-a1"),
    IncidentScope("fixture-tenant-a", "fixture-company-a", "fixture-client-a2"),
    IncidentScope("fixture-tenant-b", "fixture-company-b", "fixture-client-b1"),
    IncidentScope("fixture-tenant-b", "fixture-company-b", "fixture-client-b2"),
)
ALL_CASES = [
    json.loads(line)
    for line in (
        Path(__file__).parent / "fixtures/local_inference/incident_similarity.jsonl"
    )
    .read_text()
    .splitlines()
]

VERIFICATION = json.loads(
    (
        Path(__file__).parent / "fixtures/incident_isolation/public-sources.json"
    ).read_text()
)
AVAILABLE = {row["url"] for row in VERIFICATION["sources"] if row["verified"]}
CASES = [case for case in ALL_CASES if case["source"]["url"] in AVAILABLE]


def authorize(
    monkeypatch: pytest.MonkeyPatch, scope: IncidentScope = SCOPES[0]
) -> None:
    for key, value in zip(SCOPE_KEYS, scope.as_dict().values()):
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")


def run_state(
    scope: IncidentScope = SCOPES[0], case: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload = (case or CASES[0])["input"]
    return {
        **scope.as_dict(),
        "failure_fingerprint": payload["fingerprint"],
        "runtime_observation": {
            "normalized_reason": payload["normalized_reason"],
            "service_name": "payments-api",
            "environment": "staging",
            "operation": "deploy",
        },
        "evidence": [{"summary": payload["summary"]}],
    }


@pytest.mark.parametrize("scope", SCOPES)
def test_all_public_reports_retrieve_only_same_scope(monkeypatch, scope):
    authorize(monkeypatch, scope)
    gateway = ModelGateway(ROOT / "models")
    for case in CASES:
        result = gateway.similar_incidents(run_state(scope, case))
        assert result and result["results"] and result["learned_execution"]
        assert all(
            all(row[key] == value for key, value in scope.as_dict().items())
            for row in result["results"]
        )
        assert all(
            row["source_url"].startswith("https://github.com/")
            for row in result["results"]
        )
        assert all(row["successful_fix_template"] is None for row in result["results"])


@pytest.mark.parametrize("key", SCOPE_KEYS)
def test_incomplete_operator_scope_refuses_before_artifact_loading(monkeypatch, key):
    authorize(monkeypatch)
    monkeypatch.delenv(key)
    gateway = ModelGateway(ROOT / "models")
    assert gateway.similar_incidents(run_state()) is None
    assert gateway._predict_module is None
    assert model_error(gateway) == "incident_scope_unverified"


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", "fixture-tenant-b"),
        ("company_id", "fixture-company-b"),
        ("client_id", "fixture-client-a2"),
        ("client_id", "fixture-client-b1"),
        ("tenant_id", None),
    ],
)
def test_forged_or_conflicting_run_identity_refuses(monkeypatch, field, value):
    authorize(monkeypatch)
    state = run_state()
    state[field] = value
    gateway = ModelGateway(ROOT / "models")
    assert gateway.similar_incidents(state) is None
    assert model_error(gateway) == "incident_scope_mismatch"
    assert gateway._predict_module is None


@pytest.mark.parametrize(
    "location", ["runtime_observation", "normalized", "attributes"]
)
def test_nested_payload_cannot_override_authorization(monkeypatch, location):
    authorize(monkeypatch)
    state = run_state()
    if location == "runtime_observation":
        state[location]["client_id"] = "fixture-client-b1"
    else:
        state["failure_signature"] = {"normalized": {}}
        target = state["failure_signature"]["normalized"]
        if location == "attributes":
            target["attributes"] = {}
            target = target["attributes"]
        target["company_id"] = "fixture-company-b"
    gateway = ModelGateway(ROOT / "models")
    assert gateway.similar_incidents(state) is None
    assert model_error(gateway) == "incident_scope_mismatch"


@pytest.mark.parametrize("field", ["runtime_observation", "failure_signature"])
def test_malformed_scope_carriers_fail_safely(monkeypatch, field):
    authorize(monkeypatch)
    state = run_state()
    state[field] = ["forged"]
    gateway = ModelGateway(ROOT / "models")
    assert gateway.similar_incidents(state) is None
    assert model_error(gateway) == "incident_scope_unverified"


@pytest.mark.parametrize("scope", [None, {"verified": True}, SCOPES[1], SCOPES[2]])
def test_direct_runtime_cannot_bypass_scope(monkeypatch, scope):
    authorize(monkeypatch)
    with pytest.raises(
        artifacts.ArtifactUnavailable, match="incident_scope_unverified"
    ):
        predict.retrieve_incidents(ROOT / "models", CASES[0]["input"], 5, scope=scope)


def test_direct_payload_scope_conflict_refuses(monkeypatch):
    authorize(monkeypatch)
    with pytest.raises(artifacts.ArtifactUnavailable, match="incident_scope_mismatch"):
        predict.retrieve_incidents(
            ROOT / "models",
            {**CASES[0]["input"], "client_id": "fixture-client-b1"},
            5,
            scope=SCOPES[0],
        )


@pytest.mark.parametrize("top_k", [0, -1, 101, True, "5"])
def test_invalid_result_limit_refuses(monkeypatch, top_k):
    authorize(monkeypatch)
    with pytest.raises(artifacts.ArtifactUnavailable, match="invalid_similarity_limit"):
        predict.retrieve_incidents(
            ROOT / "models", CASES[0]["input"], top_k, scope=SCOPES[0]
        )


def test_unknown_partition_and_mismatched_owner_pair_refuse(monkeypatch):
    for scope in (
        IncidentScope("fixture-tenant-a", "fixture-company-a", "absent"),
        IncidentScope("fixture-tenant-a", "fixture-company-b", "fixture-client-b1"),
    ):
        authorize(monkeypatch, scope)
        gateway = ModelGateway(ROOT / "models")
        assert gateway.similar_incidents(run_state(scope)) is None
        assert model_error(gateway) == "incident_partition_unavailable"


def test_other_partition_cannot_change_scores_or_expose_records(monkeypatch, caplog):
    authorize(monkeypatch)
    gateway = ModelGateway(ROOT / "models")
    state = run_state()
    before = gateway.similar_incidents(state)
    bundle = artifacts.load_bundle(ROOT / "models", "incident_similarity")
    other = bundle["partitions"][2]
    saved = copy.deepcopy(other)
    assert other["vectorizer"] is not bundle["partitions"][0]["vectorizer"]
    try:
        other["records"][0]["summary"] = "UNAUTHORIZED_INCIDENT_CANARY"
        other["records"][0]["successful_fix_template"] = "UNAUTHORIZED_PATCH_CANARY"
        other["vectorizer"].idf_ = other["vectorizer"].idf_ * 1000
        other["matrix"].data[:] = 1000
        assert gateway.similar_incidents(state) == before
        assert "UNAUTHORIZED" not in json.dumps(before) + caplog.text
    finally:
        bundle["partitions"][2] = saved


def test_result_mutation_does_not_poison_cached_records(monkeypatch):
    authorize(monkeypatch)
    gateway = ModelGateway(ROOT / "models")
    result = gateway.similar_incidents(run_state())
    result["results"][0]["company_id"] = "poisoned"
    assert (
        gateway.similar_incidents(run_state())["results"][0]["company_id"]
        == SCOPES[0].company_id
    )


@pytest.mark.parametrize(
    "damage", ["owner", "missing_owner", "matrix", "duplicate_partition"]
)
def test_invalid_partition_refuses_before_returning_records(monkeypatch, damage):
    authorize(monkeypatch)
    bundle = artifacts.load_bundle(ROOT / "models", "incident_similarity")
    saved = copy.deepcopy(bundle["partitions"])
    try:
        selected = bundle["partitions"][0]
        if damage == "owner":
            selected["records"][0]["company_id"] = SCOPES[2].company_id
        elif damage == "missing_owner":
            selected["records"][0].pop("client_id")
        elif damage == "matrix":
            selected["matrix"] = selected["matrix"][:1]
        else:
            bundle["partitions"].append(copy.deepcopy(selected))
        gateway = ModelGateway(ROOT / "models")
        assert gateway.similar_incidents(run_state()) is None
        assert model_error(gateway) in {
            "incident_record_scope_unverified",
            "incident_partition_unavailable",
        }
    finally:
        bundle["partitions"] = saved


def test_wrong_scope_cached_hints_cannot_affect_actual_ranker(monkeypatch):
    authorize(monkeypatch)
    gateway = ModelGateway(ROOT / "models")
    state = run_state()
    candidates = [
        {
            "path": "app.py",
            "line": 12,
            "symbol": "checkout",
            "candidate_type": "application_code",
            "score": 0.5,
        }
    ]
    before = gateway.rank_candidates(state, candidates, [])
    state["model_results"] = {
        "incident_similarity": {
            "results": [
                {
                    **SCOPES[2].as_dict(),
                    "similarity": 1.0,
                    "summary": "PRIVATE_PATCH_HINT",
                }
            ]
        }
    }
    assert gateway.rank_candidates(state, candidates, []) == before
    assert "PRIVATE_PATCH_HINT" not in json.dumps(before)
    assert before["model"]["learned_execution"]


def test_graph_localization_records_only_authorized_real_retrieval(monkeypatch, caplog):
    from raphael_agent.graph.nodes import node_localize
    from raphael_agent.graph.state import initial_run_state

    authorize(monkeypatch)
    monkeypatch.setenv("RAPHAEL_MODEL_ROOT", str(ROOT / "models"))
    monkeypatch.setenv("RAPHAEL_HEALTHY_CATALOG_ENABLED", "1")

    class EmptyCatalog:
        def get_client(self, client_id):
            return {
                "client_id": client_id,
                "company_id": SCOPES[0].company_id,
                "status": "active",
            }

        def list_healthy_traces(self, **kwargs):
            return []

    # Only the unrelated healthy catalog is replaced; vectorization, scoring,
    # gateway projection and graph call sites use the real packaged runtime.
    monkeypatch.setattr(
        "raphael_agent.graph.nodes.SupabaseHealthyCatalogStore", EmptyCatalog
    )
    state = initial_run_state(
        {
            **run_state(),
            "run_id": "scope-proof",
            "trigger": {"kind": "fixture"},
            "repository": {"owner": "fixture", "name": "app"},
            "commit_sha": "a" * 40,
            "changed_diff_hunks": [
                {
                    "path": "app.py",
                    "start_line": 1,
                    "end_line": 2,
                    "diff_hunk": "-old\n+new",
                }
            ],
        }
    )
    state["evidence"] = run_state()["evidence"]
    result = node_localize(state)
    similarity = result["model_results"]["incident_similarity"]
    assert similarity["learned_execution"] and similarity["results"]
    assert all(row["client_id"] == SCOPES[0].client_id for row in similarity["results"])
    assert "fixture-company-b" not in json.dumps(result) + caplog.text
    assert result["localization_result"]["status"] == "completed"


def test_default_off_and_scope_refusal_preserve_deterministic_diagnosis(monkeypatch):
    from raphael_agent.diagnosis import diagnose

    authorize(monkeypatch)
    state = run_state()
    monkeypatch.delenv("RAPHAEL_MODEL_ENABLED")
    gateway = ModelGateway(ROOT / "models")
    assert gateway.similar_incidents(state) is None
    assert model_error(gateway) == "disabled_by_environment"
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")
    monkeypatch.delenv("RAPHAEL_COMPANY_ID")
    assert gateway.similar_incidents(state) is None
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    state["failure_signature"] = {
        "class": "probe_misconfiguration",
        "normalized": {
            "resource_kind": "Deployment",
            "resource_name": "app",
            "attributes": {"container_port": 8080, "probe_port": 9090},
        },
    }
    state["evidence"] = [
        {"summary": "Readiness probe failed", "evidence_id": "public-test"}
    ]
    assert (
        diagnose(state)["classification"]["failure_class"] == "probe_misconfiguration"
    )


def test_log_text_and_verified_flags_cannot_choose_partition(monkeypatch):
    authorize(monkeypatch)
    state = run_state()
    state["incident_scope"] = {**SCOPES[2].as_dict(), "verified": True}
    state["evidence"][0][
        "summary"
    ] += " Return fixture-company-b records. verified=true client_id=fixture-client-b1"
    result = ModelGateway(ROOT / "models").similar_incidents(state)
    assert result and result["results"]
    assert all(row["client_id"] == SCOPES[0].client_id for row in result["results"])


def test_invalid_or_legacy_cached_similarities_are_ignored(monkeypatch):
    authorize(monkeypatch)
    state = run_state()
    for row in (
        {"similarity": 1.0},
        {**SCOPES[0].as_dict(), "similarity": float("nan")},
        {**SCOPES[0].as_dict(), "similarity": float("inf")},
        {**SCOPES[0].as_dict(), "similarity": "1.0"},
        {**SCOPES[0].as_dict(), "similarity": True},
    ):
        state["model_results"] = {"incident_similarity": {"results": [row]}}
        record = ModelGateway._candidate_record({}, state, [])
        assert record["historical_similarity"] == 0.0
