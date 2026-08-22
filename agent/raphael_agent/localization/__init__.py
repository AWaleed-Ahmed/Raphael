"""Fault Localization Engine (FLE) for Raphael.

Combines runtime release resolution, runtime anchor extraction, deterministic candidate scoring,
and counterfactual sandbox interventions.
"""

from __future__ import annotations

from raphael_agent.localization.anchors import (
    DeploymentIdentity,
    RuntimeAnchor,
    extract_kubernetes_manifest_anchors,
    extract_route_to_handler_anchor,
    extract_stack_trace_anchors,
    extract_trace_divergence_anchor,
    resolve_deployment_identity,
)
from raphael_agent.localization.candidates import (
    CandidateScorer,
    FaultCandidate,
)
from raphael_agent.localization.catalog import (
    CatalogEntry,
    HealthyCatalogStore,
)
from raphael_agent.localization.supabase_catalog import (
    HealthyTraceComparison,
    SupabaseCatalogError,
    SupabaseHealthyCatalogStore,
    compare_trace_to_healthy,
)

from raphael_agent.localization.code_evidence import (
    build_dependency_graph,
    coverage_relevance,
    dependency_relevance,
    load_coverage,
)

from raphael_agent.localization.source_resolver import required_oci_labels, resolve_anchor

from raphael_agent.localization.interventions import (
    InterventionResult,
    SandboxInterventionController,
)

__all__ = [
    "CatalogEntry",
    "HealthyCatalogStore",
    "DeploymentIdentity",
    "RuntimeAnchor",
    "resolve_deployment_identity",
    "extract_stack_trace_anchors",
    "extract_trace_divergence_anchor",
    "extract_route_to_handler_anchor",
    "extract_kubernetes_manifest_anchors",
    "FaultCandidate",
    "CandidateScorer",
    "InterventionResult",
    "SandboxInterventionController",
    "HealthyTraceComparison",
    "SupabaseCatalogError",
    "SupabaseHealthyCatalogStore",
    "compare_trace_to_healthy",
    "load_coverage",
    "coverage_relevance",
    "build_dependency_graph",
    "dependency_relevance",
    "required_oci_labels",
    "resolve_anchor",
]
