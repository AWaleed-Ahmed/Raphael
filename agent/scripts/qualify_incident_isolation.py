"""Replay public incident reports through the real scoped retrieval gateway."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

from raphael_agent.incident_scope import IncidentScope
from raphael_agent.local_inference.artifacts import TRUSTED_ARTIFACTS
from raphael_agent.model_gateway import ModelGateway, model_error

SCOPES = (
    IncidentScope("fixture-tenant-a", "fixture-company-a", "fixture-client-a1"),
    IncidentScope("fixture-tenant-a", "fixture-company-a", "fixture-client-a2"),
    IncidentScope("fixture-tenant-b", "fixture-company-b", "fixture-client-b1"),
    IncidentScope("fixture-tenant-b", "fixture-company-b", "fixture-client-b2"),
)


def qualify(
    model_root: Path, cases_path: Path, verification_path: Path
) -> dict[str, Any]:
    """Assert authorization and record reproducible outputs, without model stubs."""
    verification = json.loads(verification_path.read_text())
    assert (
        hashlib.sha256(cases_path.read_bytes()).hexdigest()
        == verification["fixture_sha256"]
    )
    available = {row["url"] for row in verification["sources"] if row["verified"]}
    cases = [
        case
        for line in cases_path.read_text().splitlines()
        if (case := json.loads(line))["source"]["url"] in available
    ]
    reports = []
    for scope in SCOPES:
        env = {
            "RAPHAEL_MODEL_ENABLED": "1",
            "RAPHAEL_AGENT_TENANT_ID": scope.tenant_id,
            "RAPHAEL_COMPANY_ID": scope.company_id,
            "RAPHAEL_CLIENT_ID": scope.client_id,
        }
        predictions = []
        denials = 0
        with patch.dict(os.environ, env):
            gateway = ModelGateway(model_root)
            for case in cases:
                payload = case["input"]
                state = {
                    **scope.as_dict(),
                    "failure_fingerprint": payload["fingerprint"],
                    "runtime_observation": {
                        "normalized_reason": payload["normalized_reason"],
                        "service_name": "payments-api",
                    },
                    "evidence": [{"summary": payload["summary"]}],
                }
                result = gateway.similar_incidents(state)
                assert result and result["results"] and result["learned_execution"]
                assert all(
                    all(row[key] == value for key, value in scope.as_dict().items())
                    for row in result["results"]
                )
                assert result["results"][0]["source_url"] == case["source"]["url"]
                predictions.append(
                    {"query_source": case["source"]["url"], "result": result}
                )
                for field in ("tenant_id", "company_id", "client_id"):
                    assert (
                        gateway.similar_incidents({**state, field: "forged-scope"})
                        is None
                    )
                    assert model_error(gateway) == "incident_scope_mismatch"
                    denials += 1
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
            assert before and before["model"]["learned_execution"]
            foreign = (
                SCOPES[2] if scope.company_id == SCOPES[0].company_id else SCOPES[0]
            )
            untrusted = {
                **state,
                "model_results": {
                    "incident_similarity": {
                        "results": [
                            {
                                **foreign.as_dict(),
                                "similarity": 1.0,
                                "summary": "FOREIGN_PATCH_CANARY",
                            }
                        ]
                    }
                },
            }
            assert gateway.rank_candidates(untrusted, candidates, []) == before
            assert gateway._invoke("retrieve_incidents", payload) is None
            assert model_error(gateway) == "incident_scope_unverified"
            sample = predictions[0]
            reports.append(
                {
                    "scope": scope.as_dict(),
                    "authorized_queries": len(predictions),
                    "forged_scope_denials": denials,
                    "wrong_scope_ranking_unchanged": True,
                    "direct_unscoped_call_refused": True,
                    "sample_query_source": sample["query_source"],
                    "sample_top_match": {
                        key: sample["result"]["results"][0][key]
                        for key in ("incident_id", "source_url", "similarity")
                    },
                    "predictions_sha256": hashlib.sha256(
                        json.dumps(predictions, sort_keys=True).encode()
                    ).hexdigest(),
                }
            )
    with patch.dict(os.environ, {"RAPHAEL_MODEL_ENABLED": "0"}):
        gateway = ModelGateway(model_root)
        assert gateway.similar_incidents(state) is None
        assert model_error(gateway) == "disabled_by_environment"
    return {
        "passed": True,
        "public_source_reports": len(cases),
        "test_partitions": len(SCOPES),
        "artifact_identity": TRUSTED_ARTIFACTS["incident_similarity"],
        "source_verification_sha256": hashlib.sha256(
            verification_path.read_bytes()
        ).hexdigest(),
        "excluded_source_urls": [
            row["url"] for row in verification["sources"] if not row["verified"]
        ],
        "partitions": reports,
        "default_off_preserved": True,
        "limits": [
            "Public reports; tenant/company/client ownership is explicitly synthetic.",
            "Four partitions repeat 49 reports, not 196 independent incidents.",
            "In-sample retrieval and isolation proof, not root-cause accuracy or customer rollout.",
            "Only environment configuration is patched; no predictions or vectorizers are stubbed.",
        ],
    }


def main() -> None:
    """Write the isolation report for explicitly supplied artifacts and fixtures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--source-verification", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = qualify(args.model_root, args.cases, args.source_verification)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
