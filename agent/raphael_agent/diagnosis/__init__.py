"""Structured diagnosis — deterministic analyzers first, optional LLM refine."""

from __future__ import annotations

from typing import Any

from raphael_agent.diagnosis.analyzers import AnalyzerHit, analyze_run
from raphael_agent.diagnosis.config import confidence_threshold
from raphael_agent.diagnosis.llm import try_llm_diagnosis
from raphael_agent.schema_util import validate_agent
from raphael_agent.timeutil import utc_now

__all__ = ["diagnose", "stub_diagnose", "analyze_run", "confidence_threshold"]


def _hit_to_hypothesis(hit: AnalyzerHit, rank: int) -> dict[str, Any]:
    return {
        "hypothesis_id": hit.hypothesis_id,
        "rank": rank,
        "statement": hit.statement,
        "confidence": hit.confidence,
        "failure_class": hit.failure_class,
        "expected_signature_key": hit.expected_signature_key,
        "supporting_evidence_ids": list(hit.supporting_evidence_ids),
        "contradicting_evidence_ids": list(hit.contradicting_evidence_ids),
        "candidate_fix_hint": hit.candidate_fix_hint,
    }


def _unknown_result(
    evidence_ids: list[str], *, threshold: float, notes: str
) -> dict[str, Any]:
    return {
        "classification": {
            "category": "unknown",
            "failure_class": "unknown",
            "blocked_reason": None,
        },
        "hypotheses": [
            {
                "hypothesis_id": "hyp-unknown",
                "rank": 1,
                "statement": "No supported deterministic failure pattern matched",
                "confidence": 0.2,
                "failure_class": "unknown",
                "expected_signature_key": None,
                "supporting_evidence_ids": evidence_ids,
                "contradicting_evidence_ids": [],
                "candidate_fix_hint": None,
            }
        ],
        "selected_hypothesis_id": None,
        "confidence": 0.0,
        "confidence_threshold": threshold,
        "supporting_evidence_ids": evidence_ids,
        "analyzer": {
            "name": "deterministic_analyzers",
            "mode": "deterministic",
            "version": "0.2.0",
        },
        "notes": notes,
        "diagnosed_at": utc_now(),
    }


def diagnose(run: dict[str, Any]) -> dict[str, Any]:
    """Produce a schema-valid diagnosis_result (analyzers first, LLM optional)."""
    threshold = confidence_threshold()
    evidence_ids = [
        str(e["evidence_id"])
        for e in (run.get("evidence") or [])
        if e.get("evidence_id")
    ]
    hits = analyze_run(run)
    hint = run.get("failure_class_hint")
    is_issue = (run.get("trigger") or {}).get("kind") == "github_issue" or run.get(
        "delivery_mode"
    ) == "issue_snippet"

    # Route B: explicit failure-class hint in the issue body.
    if is_issue and hint and not any(h.failure_class == hint for h in hits):
        from raphael_agent.diagnosis.analyzers import AnalyzerHit

        hits = [
            AnalyzerHit(
                failure_class=str(hint),
                category="supported",
                confidence=max(threshold, 0.75),
                statement=f"Issue requested failure class `{hint}`",
                hypothesis_id=f"hyp-issue-{hint}",
                expected_signature_key=None,
                candidate_fix_hint="Use template or model patch for requested class",
                supporting_evidence_ids=evidence_ids,
                analyzer_name="issue_failure_class_hint",
            )
        ] + list(hits)

    if not hits:
        result = _unknown_result(
            evidence_ids,
            threshold=threshold,
            notes="No analyzer hit; escalate unless LLM is enabled and succeeds",
        )
    else:
        top = hits[0]
        hypotheses = [
            _hit_to_hypothesis(hit, rank=i + 1) for i, hit in enumerate(hits[:3])
        ]
        selected_id = None
        confidence = 0.0
        if top.category == "blocked":
            selected_id = None
            confidence = top.confidence
        elif top.category == "supported" and top.confidence >= threshold:
            selected_id = top.hypothesis_id
            confidence = top.confidence
        else:
            selected_id = None
            confidence = top.confidence if top.category == "supported" else 0.0

        result = {
            "classification": {
                "category": top.category,
                "failure_class": top.failure_class,
                "blocked_reason": top.blocked_reason,
            },
            "hypotheses": hypotheses,
            "selected_hypothesis_id": selected_id,
            "confidence": confidence if selected_id else (
                top.confidence if top.category == "blocked" else 0.0
            ),
            "confidence_threshold": threshold,
            "supporting_evidence_ids": list(top.supporting_evidence_ids) or evidence_ids,
            "analyzer": {
                "name": top.analyzer_name,
                "mode": "deterministic",
                "version": "0.2.0",
            },
            "notes": "Deterministic analyzers only" if selected_id or top.category == "blocked" else (
                "Leading hypothesis below confidence threshold"
            ),
            "diagnosed_at": utc_now(),
        }
        # For blocked, keep confidence as the blocked hit confidence for audit.
        if top.category == "blocked":
            result["confidence"] = top.confidence
            result["selected_hypothesis_id"] = None
            result["notes"] = top.blocked_reason or "blocked category"

    # Optional LLM refine (never overrides blocked).
    if result["classification"]["category"] != "blocked":
        refined = try_llm_diagnosis(run, result)
        if refined is not None:
            # Re-apply selection gate in code.
            conf = float(refined.get("confidence") or 0)
            thr = float(refined.get("confidence_threshold") or threshold)
            category = (refined.get("classification") or {}).get("category")
            if category == "blocked" or conf < thr:
                refined["selected_hypothesis_id"] = None
                if category != "blocked":
                    refined["confidence"] = 0.0
            result = refined

    # Route B + model patch: allow a synthetic supported selection so graph reaches patch.
    if (
        is_issue
        and result.get("selected_hypothesis_id") is None
        and (result.get("classification") or {}).get("category") != "blocked"
    ):
        from raphael_agent.patch.llm import llm_patch_enabled

        if llm_patch_enabled():
            result = {
                "classification": {
                    "category": "supported",
                    "failure_class": hint or "issue_model_fix",
                    "blocked_reason": None,
                },
                "hypotheses": [
                    {
                        "hypothesis_id": "hyp-issue-model",
                        "rank": 1,
                        "statement": "Labeled issue requested a model-assisted fix",
                        "confidence": max(threshold, 0.7),
                        "failure_class": hint or "issue_model_fix",
                        "expected_signature_key": None,
                        "supporting_evidence_ids": evidence_ids,
                        "contradicting_evidence_ids": [],
                        "candidate_fix_hint": "LLM patch under fix_rules",
                    }
                ],
                "selected_hypothesis_id": "hyp-issue-model",
                "confidence": max(threshold, 0.7),
                "confidence_threshold": threshold,
                "supporting_evidence_ids": evidence_ids,
                "analyzer": {
                    "name": "issue_model_gate",
                    "mode": "hybrid",
                    "version": "0.1.0",
                },
                "notes": "Issue route with RAPHAEL_LLM_PATCH enabled",
                "diagnosed_at": utc_now(),
            }

    from raphael_agent.learning import apply_learning_to_diagnosis

    result = apply_learning_to_diagnosis(run, result)
    validate_agent("diagnosis_result.json", result)
    return result


# Back-compat alias used by older imports/tests
def stub_diagnose(run: dict[str, Any]) -> dict[str, Any]:
    return diagnose(run)
