"""Model-layer adapters for the optional local Raphael classifiers.

The model package is intentionally kept separate from the agent package.  This
module is the boundary between provider-neutral ``RunState`` data and the
JSON-friendly model functions in ``raphael/model/predict.py``.  Models are
best-effort: deterministic analyzers and sandbox policy remain authoritative
when artifacts or runtime dependencies are unavailable.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_ROOT = REPO_ROOT / "models"
MODEL_SCRIPT = REPO_ROOT / "raphael" / "model" / "predict.py"

# The model classifier uses a slightly broader taxonomy than the public agent
# diagnosis contract.  Keep the conversion explicit and fail closed for labels
# that cannot be represented without inventing a new contract value.
DIAGNOSIS_CLASS_MAP = {
    "resource_exhaustion": "resource_constraint",
    "auth_denied": "deployment_regression",
    "dependency_timeout": "deployment_regression",
    "db_error": "deployment_regression",
    "network_error": "deployment_regression",
    "latency_regression": "deployment_regression",
    "trace_divergence": "deployment_regression",
}


class ModelGateway:
    """Load model inference once and expose layer-specific adapters.

    Direct imports are used when the agent environment has the lightweight
    model dependencies installed.  Setting ``RAPHAEL_MODEL_ENABLED=0``
    disables all inference and preserves the deterministic-only path.
    """

    def __init__(self, model_root: Path | str | None = None) -> None:
        self.model_root = Path(
            model_root or os.environ.get("RAPHAEL_MODEL_ROOT") or DEFAULT_MODEL_ROOT
        ).expanduser().resolve()
        self._predict_module: Any | None = None
        self._load_error: str | None = None

    @property
    def enabled(self) -> bool:
        return os.environ.get("RAPHAEL_MODEL_ENABLED", "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }

    def _load(self) -> Any | None:
        if not self.enabled:
            self._load_error = "disabled_by_environment"
            return None
        if self._predict_module is not None:
            return self._predict_module
        if not MODEL_SCRIPT.is_file():
            self._load_error = f"predict_script_missing:{MODEL_SCRIPT}"
            return None
        try:
            # predict.py intentionally has dependency-light sibling imports
            # (common.py/rules.py), so expose that directory while loading it.
            model_dir = str(MODEL_SCRIPT.parent)
            if model_dir not in sys.path:
                sys.path.insert(0, model_dir)
            spec = importlib.util.spec_from_file_location(
                "raphael_local_model_predict", MODEL_SCRIPT
            )
            if spec is None or spec.loader is None:
                raise ImportError("unable to create model adapter module spec")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._predict_module = module
            return module
        except Exception as exc:  # noqa: BLE001 - model path is best-effort
            self._load_error = f"{type(exc).__name__}:{exc}"
            return None

    def _invoke(self, method: str, payload: Any, *, top_k: int = 5) -> dict[str, Any] | None:
        module = self._load()
        if module is None:
            return None
        try:
            function = getattr(module, method)
            if method == "retrieve_incidents":
                result = function(self.model_root, payload, top_k)
            else:
                result = function(self.model_root, payload)
            return result if isinstance(result, dict) else None
        except Exception as exc:  # noqa: BLE001 - deterministic fallback must survive
            self._load_error = f"{type(exc).__name__}:{exc}"
            return None

    @staticmethod
    def _observation(state: dict[str, Any]) -> dict[str, Any]:
        observation = dict(state.get("runtime_observation") or {})
        signature = state.get("failure_signature") or {}
        normalized = signature.get("normalized")
        if isinstance(normalized, dict):
            for key, value in normalized.items():
                observation.setdefault(key, value)
        if signature.get("key"):
            observation.setdefault("fingerprint", signature["key"])
        if signature.get("class"):
            observation.setdefault("failure_class", signature["class"])
        return observation

    @classmethod
    def _failure_record(cls, state: dict[str, Any]) -> dict[str, Any]:
        observation = cls._observation(state)
        signature = state.get("failure_signature") or {}
        normalized = signature.get("normalized") if isinstance(signature.get("normalized"), dict) else {}
        evidence = state.get("evidence") or []
        evidence_text = " ".join(
            str(item.get("summary") or item.get("content_excerpt") or "")
            for item in evidence
            if isinstance(item, dict)
        )
        record = {
            **observation,
            "fingerprint": state.get("failure_fingerprint")
            or signature.get("key")
            or observation.get("fingerprint"),
            "normalized_reason": normalized.get("reason")
            or observation.get("normalized_reason")
            or observation.get("reason")
            or observation.get("event_reason"),
            "service_name": observation.get("service_name")
            or (state.get("correlation") or {}).get("workload"),
            "environment": observation.get("environment")
            or state.get("target_environment"),
            "evidence_text": evidence_text,
            "span_error_count": observation.get("span_error_count")
            or observation.get("error_span_count")
            or 0,
            "stack_present": bool(
                observation.get("stack_trace") or observation.get("exception.stacktrace")
            ),
            "trace_present": bool(
                observation.get("span_sequence") or observation.get("spans")
            ),
        }
        return record

    def trace_anomaly(self, state: dict[str, Any]) -> dict[str, Any] | None:
        """Adapt an APM/runtime observation to the trace anomaly model."""
        observation = self._observation(state)
        comparisons = state.get("healthy_trace_comparisons") or []
        baseline = comparisons[0] if comparisons and isinstance(comparisons[0], dict) else {}
        payload = {
            "service_name": observation.get("service_name") or "unknown",
            "operation": observation.get("operation") or observation.get("route") or "unknown",
            "span_sequence": observation.get("span_sequence") or observation.get("spans") or [],
            "latency_ms": observation.get("latency_ms") or observation.get("duration_ms") or 0,
            "error_span_count": observation.get("error_span_count")
            or observation.get("span_error_count")
            or 0,
            "status_code": observation.get("status_code") or observation.get("http_status") or 0,
        }
        if baseline:
            payload["baseline_latency_ms"] = baseline.get("latency_ms") or baseline.get("healthy_latency_ms")
            payload["baseline_error_span_count"] = baseline.get("error_span_count")
            payload["baseline_status_code"] = baseline.get("status_code")
        return self._invoke("detect_trace", payload)

    def classify_failure(self, state: dict[str, Any]) -> dict[str, Any] | None:
        """Adapt fingerprints/evidence to the failure-classifier model."""
        return self._invoke("classify_failure", self._failure_record(state))

    def similar_incidents(self, state: dict[str, Any], *, top_k: int = 5) -> dict[str, Any] | None:
        """Adapt the current incident to the historical similarity model."""
        return self._invoke("retrieve_incidents", self._failure_record(state), top_k=top_k)

    @staticmethod
    def _candidate_record(
        candidate: dict[str, Any], state: dict[str, Any], comparisons: list[dict[str, Any]]
    ) -> dict[str, Any]:
        methods = set(candidate.get("mapping_methods") or [])
        diff_hunk = candidate.get("diff_hunk")
        failure_class = (
            ((state.get("diagnosis") or {}).get("classification") or {}).get("failure_class")
            or (state.get("failure_signature") or {}).get("class")
            or ""
        )
        return {
            "candidate_path": candidate.get("path"),
            "candidate_line": candidate.get("line", 0),
            "candidate_symbol": candidate.get("symbol"),
            "candidate_type": candidate.get("candidate_type"),
            "runtime_anchor_score": candidate.get("score", 0.0),
            "stack_trace_match": int("stack_trace" in methods),
            "stack_frame_depth": 0,
            "trace_divergence_match": int("trace_divergence" in methods),
            "first_divergent_span": int("trace_divergence" in methods),
            "changed_file_match": int("deployment_diff" in methods),
            "changed_line_overlap": int(bool(diff_hunk)),
            "route_handler_match": int("route_to_handler" in methods),
            "log_callsite_match": int("log_template" in methods),
            "failure_class_compatible": int(bool(failure_class)),
            "historical_similarity": max(
                [float(item.get("confidence") or 0.0) for item in comparisons]
                + [
                    float(item.get("similarity") or 0.0)
                    for item in ((state.get("model_results") or {}).get("incident_similarity") or {}).get("results", [])
                    if isinstance(item, dict)
                ]
                or [0.0]
            ),
            "dependency_distance": 0 if diff_hunk else 1,
        }

    def rank_candidates(
        self, state: dict[str, Any], candidates: list[dict[str, Any]], comparisons: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Rank canonical FaultCandidate rows and return contract-safe rows."""
        if not candidates:
            return None
        rows = [self._candidate_record(candidate, state, comparisons) for candidate in candidates]
        prediction = self._invoke("rank_candidates", rows)
        if not prediction:
            return None
        by_key = {
            (str(row.get("candidate_path")), int(row.get("candidate_line") or 0), str(row.get("candidate_symbol"))): row
            for row in prediction.get("candidates") or []
        }
        updated: list[dict[str, Any]] = []
        for candidate in candidates:
            key = (str(candidate.get("path")), int(candidate.get("line") or 0), str(candidate.get("symbol")))
            model_row = by_key.get(key)
            item = dict(candidate)
            if model_row is not None:
                item["score"] = round(float(model_row.get("model_score") or candidate.get("score") or 0.0), 4)
                if float(model_row.get("evidence_score") or 0.0) > 0:
                    methods = list(item.get("mapping_methods") or [])
                    if "historical_similarity" not in methods and float(model_row.get("evidence_score") or 0) >= 0.5:
                        methods.append("historical_similarity")
                    item["mapping_methods"] = methods
            updated.append(item)
        updated.sort(key=lambda row: float(row.get("score") or 0.0), reverse=True)
        return {"candidates": updated, "model": prediction}

    def select_patch(self, state: dict[str, Any]) -> dict[str, Any] | None:
        """Adapt diagnosis + top candidate to the bounded patch selector."""
        diagnosis = state.get("diagnosis") or {}
        classification = diagnosis.get("classification") or {}
        top = (state.get("fault_candidates") or [{}])[0]
        normalized = (state.get("failure_signature") or {}).get("normalized") or {}
        record = {
            **self._failure_record(state),
            "failure_class": classification.get("failure_class"),
            "candidate_type": top.get("candidate_type") or "kubernetes_manifest",
            "manifest_field": top.get("symbol") or "",
            "candidate_path": top.get("path") or "",
        }
        record["normalized_reason"] = normalized.get("reason") or record.get("normalized_reason")
        return self._invoke("select_patch", record)

    @staticmethod
    def merge_diagnosis(
        diagnosis: dict[str, Any], prediction: dict[str, Any] | None, state: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge a model classification without bypassing deterministic gates."""
        if not prediction or prediction.get("abstained"):
            return diagnosis
        classification = diagnosis.get("classification") or {}
        if classification.get("category") in {"supported", "blocked"} and diagnosis.get("selected_hypothesis_id"):
            return diagnosis
        raw_class = str(prediction.get("failure_class") or "")
        mapped_class = DIAGNOSIS_CLASS_MAP.get(raw_class, raw_class)
        allowed = {
            "invalid_missing_config", "bad_image_reference", "probe_misconfiguration",
            "resource_constraint", "service_port_mismatch", "helm_kustomize_render_error",
            "deployment_regression", "policy_blocked", "unknown", "healthy", "issue_model_fix",
        }
        if mapped_class not in allowed:
            return diagnosis
        confidence = float(prediction.get("confidence") or 0.0)
        if confidence <= 0:
            return diagnosis
        evidence_ids = [
            str(item.get("evidence_id"))
            for item in state.get("evidence") or []
            if isinstance(item, dict) and item.get("evidence_id")
        ]
        hypothesis_id = f"hyp-model-{mapped_class}"
        updated = dict(diagnosis)
        updated["classification"] = {
            "category": "supported",
            "failure_class": mapped_class,
            "blocked_reason": None,
        }
        updated["hypotheses"] = [{
            "hypothesis_id": hypothesis_id,
            "rank": 1,
            "statement": f"Model classified the incident as {mapped_class}",
            "confidence": min(1.0, confidence),
            "failure_class": mapped_class,
            "expected_signature_key": (state.get("failure_signature") or {}).get("key"),
            "supporting_evidence_ids": evidence_ids,
            "contradicting_evidence_ids": [],
            "candidate_fix_hint": None,
        }]
        updated["selected_hypothesis_id"] = hypothesis_id
        updated["confidence"] = confidence
        updated["confidence_threshold"] = float(diagnosis.get("confidence_threshold") or 0.7)
        updated["supporting_evidence_ids"] = evidence_ids
        updated["analyzer"] = {
            "name": "failure_classifier",
            "mode": "hybrid",
            "version": "1",
        }
        rule_evidence = prediction.get("rule_evidence") or "model_probability"
        updated["notes"] = f"Model adapter selected {mapped_class} ({rule_evidence})"
        return updated


def model_error(gateway: ModelGateway) -> str | None:
    """Expose a bounded diagnostic string for audit events."""
    return gateway._load_error

