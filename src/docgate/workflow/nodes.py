"""Graph nodes. Each is a thin wrapper over an existing module; no business logic lives here.

Every node is guarded: an exception becomes a recorded `NodeError`, and the graph routes to
`escalate`. A failure can end in "Needs a person" but never in Approve and never in a crash.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from langgraph.types import interrupt

from docgate.compare.summary import compare
from docgate.domain.config import RuleConfig
from docgate.domain.models import HumanReview, NodeError
from docgate.extraction.base import ExtractorOutput
from docgate.extraction.reconcile import reconcile
from docgate.ingest.whitespace import normalise_whitespace
from docgate.llm.provider import LLMConfigError
from docgate.reporting.report import PackReport, build_report
from docgate.review.payload import build_payload
from docgate.rules.engine import decide, escalate, run_rules
from docgate.workflow.deps import Deps
from docgate.workflow.state import PackState, describe_errors

Update = dict[str, Any]
Node = Callable[[PackState], Update]
Fallback = Callable[[str], Update]


def guarded(name: str, fn: Node, fallback: Fallback | None = None) -> Node:
    """Turn any exception into a recorded error. `fallback` supplies outputs later nodes need."""

    def run(state: PackState) -> Update:
        try:
            return fn(state)
        except LLMConfigError as exc:
            error = NodeError(node=name, kind="config", message=str(exc))
        except Exception as exc:  # no pack may crash the graph or slip through as approved
            error = NodeError(node=name, kind="error", message=f"{type(exc).__name__}: {exc}")
        update: Update = {"errors": [error]}
        if fallback:
            update.update(fallback(error.message))
        return update

    return run


def report_from_state(state: PackState, cfg: RuleConfig) -> PackReport:
    """Build the report for whatever the state holds; a paused pack gets a provisional one."""
    return build_report(
        pack_id=state["pack_id"],
        source_file=Path(state["pdf_path"]).name,
        verdict=state["verdict"],
        extraction=state.get("extraction"),
        issues=state.get("issues", []),
        comparison=state.get("comparison"),
        errors=state.get("errors", []),
        cfg=cfg,
        human_review=state["verdict"].human_review,
    )


def build_nodes(deps: Deps) -> dict[str, Node]:
    def ingest(state: PackState) -> Update:
        # The one place text enters the graph, so every reader and quote check sees the same string.
        return {"text": normalise_whitespace(deps.read_text(Path(state["pdf_path"])))}

    def extract_llm(state: PackState) -> Update:
        return {"llm_out": deps.llm.extract(state["text"], state["pack_id"])}

    def extract_regex(state: PackState) -> Update:
        return {"regex_out": deps.regex.extract(state["text"], state["pack_id"])}

    def reconcile_node(state: PackState) -> Update:
        result = reconcile(state["llm_out"], state["regex_out"], state["text"])
        return {"extraction": result.extraction, "issues": result.issues}

    def compare_pr(state: PackState) -> Update:
        return {"comparison": compare(state["extraction"], deps.pr_lines, deps.config)}

    def apply_rules(state: PackState) -> Update:
        pr = state["comparison"].pr_line
        return {"rule_results": run_rules(state["extraction"], pr, deps.config)}

    def decide_node(state: PackState) -> Update:
        return {"verdict": decide(state["rule_results"])}

    def escalate_node(state: PackState) -> Update:
        return {"verdict": escalate(describe_errors(state["errors"]))}

    def human_gate(state: PackState) -> Update:
        # Nothing may happen before interrupt(): on resume this node runs again from the top.
        verdict = state["verdict"]
        payload = build_payload(
            state["pack_id"],
            verdict,
            state.get("issues", []),
            state.get("errors", []),
            deps.config,
        )
        answer = interrupt(payload.model_dump(mode="json"))
        review = HumanReview.model_validate(answer)
        # The machine decision stays as it was; the human answer is recorded beside it.
        return {
            "human_review": review,
            "verdict": verdict.model_copy(update={"human_review": review}),
        }

    def report(state: PackState) -> Update:
        return {"report": report_from_state(state, deps.config)}

    def failed(source: str) -> Fallback:
        return lambda message: {
            ("llm_out" if source == "llm" else "regex_out"): ExtractorOutput(
                source=source, failure=message
            )
        }

    return {
        "ingest": guarded("ingest", ingest),
        "extract_llm": guarded("extract_llm", extract_llm, failed("llm")),
        "extract_regex": guarded("extract_regex", extract_regex, failed("regex")),
        "reconcile": guarded("reconcile", reconcile_node),
        "compare_pr": guarded("compare_pr", compare_pr),
        "apply_rules": guarded("apply_rules", apply_rules),
        "decide": guarded("decide", decide_node),
        "escalate": escalate_node,
        # Not guarded: the interrupt is an exception that must reach LangGraph.
        "human_gate": human_gate,
        "report": guarded("report", report),
    }
