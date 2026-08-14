"""Compile the agent LangGraph (in-memory; no checkpointer required)."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from raphael_agent.graph.nodes import (
    node_diagnose,
    node_evidence,
    node_ingest,
    node_patch,
    node_publish_or_escalate,
    node_reproduce,
    node_validate,
    route_after_validate,
)
from raphael_agent.graph.state import RunState


def build_stub_graph():
    """Happy path with patch retry: validate may loop back to patch within budget.

    Persistence: none (in-memory). ``RunState`` / ``run_record`` remains the
    inspectable source of truth (RunStore for durable ingest copies).
    """
    graph = StateGraph(RunState)
    graph.add_node("ingest", node_ingest)
    graph.add_node("evidence", node_evidence)
    graph.add_node("diagnose", node_diagnose)
    graph.add_node("reproduce", node_reproduce)
    graph.add_node("patch", node_patch)
    graph.add_node("validate", node_validate)
    graph.add_node("publish_or_escalate", node_publish_or_escalate)

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "evidence")
    graph.add_edge("evidence", "diagnose")
    graph.add_edge("diagnose", "reproduce")
    graph.add_edge("reproduce", "patch")
    graph.add_edge("patch", "validate")
    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {
            "patch": "patch",
            "publish_or_escalate": "publish_or_escalate",
            "end_escalated": "publish_or_escalate",
        },
    )
    graph.add_edge("publish_or_escalate", END)
    return graph.compile()


def run_stub_graph(initial: RunState) -> RunState:
    try:
        from raphael_agent.github_commands.check_runs import maybe_start_check_run

        maybe_start_check_run(dict(initial))
    except Exception:  # noqa: BLE001 — Checks must never fail the graph
        pass
    app = build_stub_graph()
    result = app.invoke(initial)
    return result  # type: ignore[return-value]
