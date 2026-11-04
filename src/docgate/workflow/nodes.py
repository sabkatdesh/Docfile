"""Graph nodes. Each is a thin wrapper over an existing module; no business logic lives here.

Every node is guarded: an exception becomes a recorded `NodeError`, and the graph routes to
`escalate`. A failure can end in "Needs a person" but never in Approve and never in a crash.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from docgate.compare.summary import compare
from docgate.domain.models import NodeError
from docgate.extraction.base import ExtractorOutput
from docgate.extraction.reconcile import reconcile
from docgate.llm.provider import LLMConfigError
from docgate.reporting.report import build_report
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


def build_nodes(deps: Deps) -> dict[str, Node]:
    def ingest(state: PackState) -> Update:
        return {"text": deps.read_text(Path(state["pdf_path"]))}

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

    def human_gate(_state: PackState) -> Update:
        # Placeholder: M4 replaces this body with interrupt(). The edges stay as they are.
        return {}

    def report(state: PackState) -> Update:
        pdf = Path(state["pdf_path"])
        built = build_report(
            pack_id=state["pack_id"],
            source_file=pdf.name,
            verdict=state["verdict"],
            extraction=state.get("extraction"),
            issues=state.get("issues", []),
            comparison=state.get("comparison"),
            errors=state.get("errors", []),
            cfg=deps.config,
        )
        return {"report": built}

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
        "human_gate": guarded("human_gate", human_gate),
        "report": guarded("report", report),
    }
