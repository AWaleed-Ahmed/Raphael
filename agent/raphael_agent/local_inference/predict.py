"""Run local inference against Raphael model artifacts using JSON input."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from sklearn.preprocessing import normalize

from .artifacts import load_bundle
from .features import feature_matrix, stable_text
from .rules import (
    candidate_evidence_score,
    deterministic_failure_class,
    rule_patch_template,
)


def matrix(
    bundle: dict[str, Any],
    rows: list[dict[str, Any]],
    prefix: dict[str, Any] | None = None,
) -> Any:
    source = prefix or bundle
    return feature_matrix(
        rows=rows,
        text_fields=source.get("text_fields") or bundle.get("text_fields") or (),
        numeric_fields=source.get("numeric_fields")
        or bundle.get("numeric_fields")
        or (),
        vectorizer=source["vectorizer"],
        means=source.get("numeric_means") or (),
        scales=source.get("numeric_scales") or (),
    )


def classify_failure(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    bundle = load_bundle(root, "failure_classifier")
    probabilities = bundle["classifier"].predict_proba(matrix(bundle, [record]))[0]
    ranked = sorted(
        zip(bundle["classifier"].classes_, probabilities),
        key=lambda item: item[1],
        reverse=True,
    )
    label, confidence = ranked[0]
    threshold = float(bundle["minimum_confidence"])
    reason = str(record.get("normalized_reason") or "")
    prefix = str(record.get("fingerprint") or "").split(":", 1)[0]
    recognized = reason in set(
        bundle.get("known_normalized_reasons") or []
    ) or prefix in set(bundle.get("known_fingerprint_prefixes") or [])
    rule_label, rule_evidence = deterministic_failure_class(record)
    # An exact normalized reason/fingerprint is stronger than incidental model
    # features. Unknown evidence still abstains instead of guessing.
    abstained = bool(confidence < threshold or not recognized) and rule_label is None
    effective_label = rule_label or (str(label) if not abstained else None)
    return {
        "learned_execution": True,
        "failure_class": effective_label if not abstained else None,
        "abstained": abstained,
        "abstention_reason": (
            "out_of_distribution"
            if not recognized
            else "low_confidence" if confidence < threshold else None
        ),
        "confidence": round(float(confidence), 6),
        "minimum_confidence": threshold,
        "rule_based": rule_label is not None,
        "rule_evidence": rule_evidence,
        "model_failure_class": str(label),
        "alternatives": [
            {"failure_class": str(name), "confidence": round(float(score), 6)}
            for name, score in ranked[:3]
        ],
    }


def rank_candidates(root: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    bundle = load_bundle(root, "candidate_ranker")
    aliases = bundle.get("candidate_type_aliases") or {}
    normalized_rows = []
    for row in rows:
        current = dict(row)
        current["candidate_type"] = aliases.get(
            current.get("candidate_type"), current.get("candidate_type")
        )
        normalized_rows.append(current)
    probabilities = bundle["classifier"].predict_proba(matrix(bundle, normalized_rows))
    positive_index = list(bundle["classifier"].classes_).index(bundle["positive_class"])
    ranked_rows = []
    for row, probability in zip(rows, probabilities[:, positive_index]):
        # Blend learned score with portable evidence. This prevents a path-name
        # prior from outranking an actual stack/trace anchor.
        evidence = candidate_evidence_score(row)
        score = 0.35 * float(probability) + 0.65 * evidence
        ranked_rows.append(
            {
                **row,
                "model_score": round(float(score), 6),
                "learned_score": round(float(probability), 6),
                "evidence_score": round(float(evidence), 6),
            }
        )
    ranked = sorted(ranked_rows, key=lambda row: row["model_score"], reverse=True)
    return {"candidates": ranked, "learned_execution": True}


def retrieve_incidents(
    root: Path, record: dict[str, Any], top_k: int
) -> dict[str, Any]:
    bundle = load_bundle(root, "incident_similarity")
    text = stable_text(record, bundle["text_fields"])
    query = normalize(bundle["vectorizer"].transform([text]), norm="l2")
    similarities = np.asarray((query @ bundle["matrix"].T).toarray()[0])
    minimum = float(bundle["minimum_similarity"])
    results = []
    for position in np.argsort(-similarities)[:top_k]:
        score = float(similarities[position])
        if score < minimum:
            continue
        results.append(
            {**bundle["records"][int(position)], "similarity": round(score, 6)}
        )
    return {
        "results": results,
        "minimum_similarity": minimum,
        "learned_execution": True,
    }


def select_patch(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    bundle = load_bundle(root, "patch_selector")
    if str(record.get("failure_class")) not in set(
        bundle.get("known_failure_classes") or []
    ) or str(record.get("candidate_type")) not in set(
        bundle.get("known_candidate_types") or []
    ):
        return {
            "policy_allowed": False,
            "reason": "out_of_distribution",
            "learned_execution": False,
        }
    template = bundle["template"]
    rule_template, rule_evidence = rule_patch_template(record)
    if rule_template:
        known_templates = {str(value) for value in template["classifier"].classes_}
        if rule_template in known_templates and rule_template not in set(
            bundle["hard_deny_templates"]
        ):
            return {
                "policy_allowed": True,
                "learned_execution": False,
                "allowed_probability": 0.99,
                "template_confidence": 0.99,
                "safe_template": rule_template,
                "rule_based": True,
                "rule_evidence": rule_evidence,
                "alternatives_evaluated": [],
                "requires_sandbox_validation": True,
            }
    template_probability = template["classifier"].predict_proba(
        matrix(bundle, [record], template)
    )[0]
    order = np.argsort(-template_probability)[: int(template.get("top_k", 3))]
    policy = bundle["policy"]
    allowed_index = list(policy["classifier"].classes_).index(1)
    threshold = float(policy["allowed_threshold"])
    hard_deny = set(bundle["hard_deny_templates"])
    evaluated = []
    for position in order:
        candidate = str(template["classifier"].classes_[position])
        template_confidence = float(template_probability[position])
        if template_confidence < float(bundle.get("minimum_template_confidence", 0.20)):
            evaluated.append(
                {
                    "template": candidate,
                    "template_confidence": round(template_confidence, 6),
                    "status": "low_confidence",
                }
            )
            continue
        if candidate in hard_deny:
            evaluated.append({"template": candidate, "status": "hard_denied"})
            continue
        policy_record = {**record, "safe_template": candidate}
        policy_probability = policy["classifier"].predict_proba(
            matrix(bundle, [policy_record], policy)
        )[0]
        allowed_probability = float(policy_probability[allowed_index])
        evaluated.append(
            {
                "template": candidate,
                "template_confidence": round(template_confidence, 6),
                "allowed_probability": round(allowed_probability, 6),
            }
        )
        if allowed_probability >= threshold:
            return {
                "policy_allowed": True,
                "learned_execution": True,
                "rule_based": False,
                "allowed_probability": round(allowed_probability, 6),
                "template_confidence": round(template_confidence, 6),
                "safe_template": candidate,
                "alternatives_evaluated": evaluated,
                "requires_sandbox_validation": True,
            }
    return {
        "policy_allowed": False,
        "learned_execution": True,
        "rule_based": False,
        "reason": "all_template_candidates_blocked_or_uncertain",
        "alternatives_evaluated": evaluated,
    }


def detect_trace(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    bundle = load_bundle(root, "trace_anomaly")
    probabilities = bundle["classifier"].predict_proba(matrix(bundle, [record]))[0]
    anomaly_index = list(bundle["classifier"].classes_).index(bundle["anomaly_class"])
    probability = float(probabilities[anomaly_index])
    threshold = float(bundle["anomaly_threshold"])
    # Healthy-trace baselines make this transferable across unseen service
    # names. The rule is only used when the caller supplies a baseline.
    baseline_latency = record.get("baseline_latency_ms")
    baseline_errors = record.get("baseline_error_span_count")
    baseline_status = record.get("baseline_status_code")
    baseline_rule = (
        int(record.get("error_span_count") or 0) > 0
        or int(record.get("status_code") or 0) >= 400
    )
    baseline_reason = "explicit_error_span_or_status" if baseline_rule else None
    if baseline_latency is not None:
        try:
            ratio = float(record.get("latency_ms") or 0.0) / max(
                float(baseline_latency), 1e-6
            )
            if ratio >= 1.5:
                baseline_rule, baseline_reason = True, "latency_vs_healthy_baseline"
        except (TypeError, ValueError):
            pass
    if baseline_errors is not None and int(record.get("error_span_count") or 0) > int(
        baseline_errors
    ):
        baseline_rule, baseline_reason = True, "new_error_spans_vs_healthy_baseline"
    if baseline_status is not None and int(record.get("status_code") or 0) >= 400 > int(
        baseline_status
    ):
        baseline_rule, baseline_reason = True, "error_status_vs_healthy_baseline"
    is_anomaly = baseline_rule or probability >= threshold
    abstained = not is_anomaly and baseline_latency is None and probability < threshold
    return {
        "is_anomaly": bool(is_anomaly),
        "learned_execution": True,
        "learned_anomaly_probability": round(probability, 6),
        "abstained": abstained,
        "abstention_reason": (
            "no_healthy_baseline_or_explicit_error" if abstained else None
        ),
        "anomaly_probability": round(
            float(max(probability, 0.99) if baseline_rule else probability), 6
        ),
        "threshold": threshold,
        "rule_based": baseline_rule,
        "rule_evidence": baseline_reason,
    }
