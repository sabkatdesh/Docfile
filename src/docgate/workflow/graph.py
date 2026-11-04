"""The fixed pipeline from SPEC section 3. Nodes and edges are explicit; there is no agent loop.

    ingest -> extract_llm   \\
                             -> reconcile -> compare_pr -> apply_rules -> decide
              extract_regex /                                              |
    any failure after ingest/reconcile/compare/rules/decide -> escalate ---+
                                                                           v
                                                        human_gate -> report -> END
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from docgate.workflow.deps import Deps
from docgate.workflow.nodes import build_nodes
from docgate.workflow.state import PackState

__all__ = ["Deps", "build_graph", "run_pack"]

_EXTRACTORS = ["extract_llm", "extract_regex"]


def _unless_failed(next_node: str) -> Callable[[PackState], str]:
    def route(state: PackState) -> str:
        return "escalate" if state.get("errors") else next_node

    return route


def _after_ingest(state: PackState) -> list[str]:
    return ["escalate"] if state.get("errors") else _EXTRACTORS


def build_graph(deps: Deps, checkpointer: BaseCheckpointSaver[Any] | None = None) -> Any:
    nodes = build_nodes(deps)
    graph: StateGraph[PackState, Any, Any, Any] = StateGraph(PackState)
    for name, fn in nodes.items():
        graph.add_node(name, cast("Any", fn))  # langgraph overloads reject plain callables

    graph.add_edge(START, "ingest")
    graph.add_conditional_edges("ingest", _after_ingest, [*_EXTRACTORS, "escalate"])
    graph.add_edge(_EXTRACTORS, "reconcile")
    for step, following in [
        ("reconcile", "compare_pr"),
        ("compare_pr", "apply_rules"),
        ("apply_rules", "decide"),
        ("decide", "human_gate"),
    ]:
        graph.add_conditional_edges(step, _unless_failed(following), [following, "escalate"])
    graph.add_edge("escalate", "human_gate")
    graph.add_edge("human_gate", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer)


def run_pack(
    graph: Any, pack_id: str, pdf_path: Path, config: dict[str, Any] | None = None
) -> PackState:
    state: PackState = graph.invoke(
        {"pack_id": pack_id, "pdf_path": str(pdf_path), "errors": []}, config
    )
    return state
