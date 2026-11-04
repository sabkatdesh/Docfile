"""Failure paths: whatever breaks, the graph ends in Needs a person, never Approve, never raises."""

from __future__ import annotations

from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from docgate.domain.models import Decision, FieldStatus
from docgate.extraction.base import ExtractorOutput
from docgate.ingest.pdf import EmptyPdfError
from docgate.llm.provider import LLMConfigError
from docgate.rules.engine import escalate
from docgate.workflow.graph import Deps, build_graph, run_pack
from docgate.workflow.state import PackState
from tests.graph_support import pack_path, replay_deps

APPROVE_PACK = 1


class Raising:
    def __init__(self, name: str, exc: Exception) -> None:
        self.name = name
        self._exc = exc

    def extract(self, text: str, label: str = "") -> ExtractorOutput:
        raise self._exc


class Failing:
    """An extractor that reports failure the way LLMExtractor does (no raise)."""

    name = "llm"

    def extract(self, text: str, label: str = "") -> ExtractorOutput:
        return ExtractorOutput(source="llm", failure="timeout after retries")


def _run(deps: Deps, path: Path | None = None) -> PackState:
    return run_pack(build_graph(deps), "p", path or pack_path(APPROVE_PACK))


def _errors(state: PackState) -> list[tuple[str, str]]:
    return [(e.node, e.kind) for e in state["errors"]]


def test_escalate_is_never_approve_and_keeps_the_reason() -> None:
    verdict = escalate("ingest failed: boom")
    assert verdict.decision is Decision.NEEDS_PERSON
    assert verdict.needs_human
    assert "boom" in verdict.reason


def test_baseline_pack_approves_without_errors() -> None:
    state = _run(replay_deps())
    assert state["verdict"].decision is Decision.APPROVE
    assert state["errors"] == []


def test_both_extractors_ran_and_reconciled() -> None:
    state = _run(replay_deps())
    assert state["llm_out"] and state["regex_out"]
    assert state["extraction"] and state["comparison"]


def test_garbage_pdf_escalates_at_ingest(tmp_path: Path) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"this is not a pdf")
    state = _run(replay_deps(), bad)
    assert state["verdict"].decision is Decision.NEEDS_PERSON
    assert _errors(state) == [("ingest", "error")]


def test_missing_file_escalates_at_ingest(tmp_path: Path) -> None:
    state = _run(replay_deps(), tmp_path / "nope.pdf")
    assert state["verdict"].decision is Decision.NEEDS_PERSON
    assert _errors(state)[0][0] == "ingest"


def test_empty_pdf_escalates_at_ingest() -> None:
    def empty(_path: Path) -> str:
        raise EmptyPdfError("no text")

    base = replay_deps()
    state = _run(Deps(base.llm, base.regex, base.pr_lines, read_text=empty))
    assert state["verdict"].decision is Decision.NEEDS_PERSON
    assert "no text" in state["verdict"].reason


def test_llm_extractor_raising_escalates() -> None:
    state = _run(replay_deps(llm=Raising("llm", RuntimeError("boom"))))
    assert state["verdict"].decision is Decision.NEEDS_PERSON
    assert ("extract_llm", "error") in _errors(state)


def test_regex_extractor_raising_escalates() -> None:
    state = _run(replay_deps(regex=Raising("regex", ValueError("bad"))))
    assert state["verdict"].decision is Decision.NEEDS_PERSON
    assert ("extract_regex", "error") in _errors(state)


def test_config_error_is_recorded_as_config_and_still_escalates() -> None:
    state = _run(replay_deps(llm=Raising("llm", LLMConfigError("bad key"))))
    assert state["verdict"].decision is Decision.NEEDS_PERSON
    assert ("extract_llm", "config") in _errors(state)


def test_extractor_reported_failure_makes_fields_unverified() -> None:
    state = _run(replay_deps(llm=Failing()))
    assert state["verdict"].decision is Decision.NEEDS_PERSON
    assert state["extraction"].unit_price.status is FieldStatus.UNVERIFIED
    assert state["errors"] == []  # handled inside reconcile, not a node crash


def test_missing_pr_line_needs_a_person() -> None:
    state = _run(replay_deps(pr_lines={}))
    assert state["verdict"].decision is Decision.NEEDS_PERSON
    assert state["errors"] == []


@pytest.mark.parametrize(
    ("node", "target"),
    [
        ("reconcile", "reconcile"),
        ("compare_pr", "compare"),
        ("apply_rules", "run_rules"),
        ("decide", "decide"),
    ],
)
def test_an_exception_in_any_node_never_approves(
    monkeypatch: pytest.MonkeyPatch, node: str, target: str
) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError(f"{node} exploded")

    monkeypatch.setattr(f"docgate.workflow.nodes.{target}", boom)
    state = _run(replay_deps())  # an Approve pack: the strongest test that failure never approves
    assert state["verdict"].decision is Decision.NEEDS_PERSON
    assert _errors(state) == [(node, "error")]
    assert f"{node} exploded" in state["verdict"].reason


def test_state_round_trips_through_a_checkpointer() -> None:
    """M4 de-risk: the full state (Pydantic, Decimal, dataclasses) must survive serialization."""
    graph = build_graph(replay_deps(), checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "pack-04"}}
    run_pack(graph, "supplier-pack-04", pack_path(4), config=config)
    saved = graph.get_state(config).values
    assert saved["verdict"].decision is Decision.NEEDS_PERSON
    assert str(saved["extraction"].unit_price.value) == "6.65"
    assert str(saved["comparison"].price_delta_pct).startswith("2.30")
