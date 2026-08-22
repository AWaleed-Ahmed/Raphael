"""Deterministic Candidate Generator & Scorer (FLE / Steps 8-10).

Scores fault candidates deterministically:
Score = 0.30(Runtime Anchor) + 0.25(Diff) + 0.20(Trace Divergence) + 0.10(Graph Proximity) + 0.10(Class Compat) + 0.05(History)
Emits top 5 ranked candidates matching contracts/agent/fault_candidate.json.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from raphael_agent.localization.anchors import RuntimeAnchor
from raphael_agent.localization.catalog import HealthyCatalogStore
from raphael_agent.schema_util import validate_agent


@dataclass
class FaultCandidate:
    """Structured candidate record identified by FLE."""

    repository: str
    git_sha: str
    path: str
    line: int
    symbol: str
    candidate_type: str  # source_code | helm_template | helm_value | kustomize_patch | kubernetes_manifest | ci_workflow | dockerfile | dependency_lockfile
    score: float
    mapping_methods: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    diff_hunk: str | None = None
    state: str = "suspected"  # suspected | localized | causal | confirmed_fix

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Ensure score is rounded float
        d["score"] = round(self.score, 4)
        return d


class CandidateScorer:
    """Calculates deterministic scores and ranks candidates."""

    # Public deterministic ranking equation (PRD):
    # stack proximity + changed deployment + first trace divergence + logs + dependency path.
    WEIGHT_STACK_PROXIMITY = 0.30
    WEIGHT_CHANGED_DEPLOYMENT = 0.25
    WEIGHT_FIRST_TRACE_DIVERGENCE = 0.20
    WEIGHT_LOG_CORRELATION = 0.15
    WEIGHT_DEPENDENCY_PATH = 0.10
    # Backward-compatible aliases for callers that imported the old names.
    WEIGHT_RUNTIME_ANCHOR = WEIGHT_STACK_PROXIMITY
    WEIGHT_DIFF = WEIGHT_CHANGED_DEPLOYMENT
    WEIGHT_TRACE_DIVERGENCE = WEIGHT_FIRST_TRACE_DIVERGENCE

    def __init__(self, catalog_store: HealthyCatalogStore | None = None) -> None:
        self.catalog_store = catalog_store or HealthyCatalogStore()

    def generate_and_rank_candidates(
        self,
        *,
        repository: str,
        git_sha: str,
        anchors: list[RuntimeAnchor],
        changed_diff_hunks: list[dict[str, Any]],
        failure_class: str = "generic_failure",
        first_divergent_anchor: RuntimeAnchor | None = None,
        workspace_path: Path | str | None = None,
    ) -> list[FaultCandidate]:
        """Rank and return top 5 candidates across all runtime anchors and git diff hunks."""
        raw_candidates: list[FaultCandidate] = []

        # 1. Index changed files and hunks
        changed_files_map: dict[str, list[dict[str, Any]]] = {}
        for hunk in changed_diff_hunks:
            p = str(hunk.get("path") or hunk.get("file_path") or "").lstrip("/")
            changed_files_map.setdefault(p, []).append(hunk)

        # 2. Build candidates from runtime anchors
        for anchor in anchors:
            c_type = self._infer_candidate_type(anchor.file_path)
            clean_path = anchor.file_path.lstrip("/")

            # Check if this anchor's file or line was changed in the failing diff
            hunks_for_file = changed_files_map.get(clean_path, [])
            diff_score = 0.0
            matched_hunk_text: str | None = None

            if hunks_for_file:
                diff_score = 0.40  # File was modified
                for h in hunks_for_file:
                    start_line = int(h.get("start_line") or h.get("line") or 0)
                    end_line = int(h.get("end_line") or start_line + 50)
                    if start_line <= anchor.line_number <= end_line or anchor.line_number == 0:
                        diff_score = 1.0  # Exact line within changed hunk!
                        matched_hunk_text = str(h.get("diff_hunk") or h.get("content") or "")
                        break

            # Check trace divergence match
            trace_score = 0.0
            mapping_methods: list[str] = []
            if anchor.signal_type == "exception":
                mapping_methods.append("stack_trace")
            elif anchor.signal_type == "trace":
                mapping_methods.append("trace_divergence")
            elif anchor.signal_type == "http":
                mapping_methods.append("route_to_handler")
            elif anchor.signal_type in {"probe", "config", "k8s_event"}:
                mapping_methods.append("manifest_provenance")
            elif anchor.signal_type == "log":
                mapping_methods.append("log_template")
            elif anchor.signal_type == "invariant":
                mapping_methods.append("invariant_violation")
            else:
                mapping_methods.append("stack_trace")

            if first_divergent_anchor and first_divergent_anchor.symbol_name == anchor.symbol_name:
                trace_score = 1.0
                if "trace_divergence" not in mapping_methods:
                    mapping_methods.append("trace_divergence")

            if diff_score > 0.0:
                mapping_methods.append("deployment_diff")


            # Deterministic evidence dimensions. Logs and dependency relevance
            # are explicit inputs when adapters provide them; exact changed-line
            # or trace anchors are strong dependency-path evidence by default.
            log_score = 1.0 if anchor.signal_type == "log" or anchor.raw_details.get("log_match") else 0.0
            dependency_score = float(anchor.raw_details.get("dependency_relevance") or 0.0)
            if dependency_score <= 0.0 and (diff_score >= 1.0 or trace_score >= 1.0):
                dependency_score = 1.0
            dependency_score = min(1.0, max(0.0, dependency_score))

            # Exact PRD equation: no learned or class prior is allowed into this
            # deterministic score. The model ranker may blend with this later.
            stack_proximity = min(1.0, anchor.confidence + (0.10 * float(anchor.raw_details.get("coverage_relevance") or 0.0)))
            total_score = (
                (self.WEIGHT_STACK_PROXIMITY * stack_proximity)
                + (self.WEIGHT_CHANGED_DEPLOYMENT * diff_score)
                + (self.WEIGHT_FIRST_TRACE_DIVERGENCE * trace_score)
                + (self.WEIGHT_LOG_CORRELATION * log_score)
                + (self.WEIGHT_DEPENDENCY_PATH * dependency_score)
            )

            # Cap between 0.0 and 1.0
            final_score = min(1.0, max(0.1, total_score))

            state = "localized" if (diff_score >= 0.4 and anchor.confidence >= 0.7) else "suspected"

            raw_candidates.append(
                FaultCandidate(
                    repository=repository,
                    git_sha=git_sha,
                    path=clean_path,
                    line=anchor.line_number,
                    symbol=anchor.symbol_name,
                    candidate_type=c_type,
                    score=final_score,
                    mapping_methods=list(set(mapping_methods)),
                    evidence_refs=[
                        anchor.evidence_ref,
                        *([f"coverage:{clean_path}:{anchor.line_number}"] if anchor.raw_details.get("coverage_relevance") else []),
                    ],
                    diff_hunk=matched_hunk_text,
                    state=state,
                )
            )

        # 3. Add changed hunks that didn't have explicit runtime anchors as secondary candidates
        for path, hunks in changed_files_map.items():
            if not any(c.path == path for c in raw_candidates):
                h = hunks[0]
                c_type = self._infer_candidate_type(path)
                # A diff-only candidate has no stack/trace/log evidence yet.
                score = self.WEIGHT_CHANGED_DEPLOYMENT * 0.7
                raw_candidates.append(
                    FaultCandidate(
                        repository=repository,
                        git_sha=git_sha,
                        path=path,
                        line=int(h.get("start_line") or 1),
                        symbol=str(h.get("symbol") or "modified_hunk"),
                        candidate_type=c_type,
                        score=min(0.85, max(0.1, score)),
                        mapping_methods=["deployment_diff"],
                        evidence_refs=["ev-git-diff"],
                        diff_hunk=str(h.get("diff_hunk") or ""),
                        state="suspected",
                    )
                )

        # Sort descending by score and pick top 5
        raw_candidates.sort(key=lambda c: c.score, reverse=True)
        top_candidates = raw_candidates[:5]

        # Validate against schema
        for cand in top_candidates:
            validate_agent("fault_candidate.json", cand.to_dict())

        return top_candidates

    def _infer_candidate_type(self, path: str) -> str:
        p = path.lower()
        if "templates/" in p or p.endswith(".tpl"):
            return "helm_template"
        if "values" in p and (p.endswith(".yaml") or p.endswith(".yml")):
            return "helm_value"
        if "kustomize" in p or "overlay" in p:
            return "kustomize_patch"
        if "manifests" in p or p.endswith(".yaml") or p.endswith(".yml"):
            return "kubernetes_manifest"
        if "dockerfile" in p:
            return "dockerfile"
        if "package-lock.json" in p or "poetry.lock" in p or "cargo.lock" in p or "go.sum" in p:
            return "dependency_lockfile"
        if ".github/workflows" in p:
            return "ci_workflow"
        return "source_code"

    def _compute_class_compatibility(self, failure_class: str, path: str, symbol: str) -> float:
        fclass = failure_class.lower()
        p = path.lower()
        if "probe" in fclass or "port" in fclass or "config" in fclass or "image" in fclass:
            return 1.0 if (p.endswith(".yaml") or p.endswith(".yml") or "docker" in p) else 0.3
        if "exception" in fclass or "crash" in fclass or "timeout" in fclass or "db" in fclass:
            return 1.0 if not (p.endswith(".yaml") or p.endswith(".yml") or p.endswith(".md")) else 0.2
        return 0.7
