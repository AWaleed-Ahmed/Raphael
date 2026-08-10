"""Compile the Phase 0 LangGraph stub (in-memory; no checkpointer)."""

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
)
from raphael_agent.graph.state import RunState


def build_stub_graph():
    """Happy path: ingest → evidence → diagnose → reproduce → patch → validate → publish_or_escalate.

    Persistence: none (in-memory). The ``RunState`` dict is the durable/inspectable
    object matching ``contracts/agent/run_record.json``; a checkpointer lands later.
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
    graph.add_edge("validate", "publish_or_escalate")
    graph.add_edge("publish_or_escalate", END)
    return graph.compile()


def run_stub_graph(initial: RunState) -> RunState:
    app = build_stub_graph()
    result = app.invoke(initial)
    return result  # type: ignore[return-value]
