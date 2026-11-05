"""Per-node progress from a real graph run. This is what the SSE stream is built on."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from docgate.domain.models import Decision
from docgate.review.checkpoint import sqlite_saver
from docgate.workflow.graph import build_graph
from docgate.workflow.progress import Finished, NodeDone, Paused, stream_pack
from tests.graph_support import pack_path, replay_deps
from tests.unit.test_workflow import Raising

ORDER = [
    "ingest",
    "extract_llm",
    "extract_regex",
    "reconcile",
    "compare_pr",
    "apply_rules",
    "decide",
]


@pytest.fixture
def saver(tmp_path: Path) -> Iterator[SqliteSaver]:
    with sqlite_saver(tmp_path / "ck.sqlite") as s:
        yield s


def _events(saver: SqliteSaver, n: int, **deps: object) -> list[object]:
    graph = build_graph(replay_deps(**deps), checkpointer=saver)  # type: ignore[arg-type]
    return list(stream_pack(graph, f"supplier-pack-{n:02d}", pack_path(n)))


def _nodes(events: list[object]) -> list[str]:
    return [e.node for e in events if isinstance(e, NodeDone)]


def test_approve_pack_reports_every_node_in_order_and_finishes(saver: SqliteSaver) -> None:
    events = _events(saver, 1)
    nodes = _nodes(events)
    assert nodes[0] == "ingest"
    assert set(nodes[1:3]) == {"extract_llm", "extract_regex"}  # run in parallel, either order
    assert nodes[3:] == ["reconcile", "compare_pr", "apply_rules", "decide", "report"]
    assert all(e.ok for e in events if isinstance(e, NodeDone))
    last = events[-1]
    assert isinstance(last, Finished)
    assert last.state["verdict"].decision is Decision.APPROVE


def test_needs_person_pack_pauses_at_the_gate_with_no_report(saver: SqliteSaver) -> None:
    events = _events(saver, 9)
    assert _nodes(events)[-1] == "decide"  # the gate itself is not a completed node
    last = events[-1]
    assert isinstance(last, Paused)
    assert last.state["verdict"].decision is Decision.NEEDS_PERSON
    assert "report" not in last.state


def test_reject_pack_is_final_without_pausing(saver: SqliteSaver) -> None:
    assert isinstance(_events(saver, 3)[-1], Finished)


def test_a_failing_node_is_reported_then_the_pack_escalates(saver: SqliteSaver) -> None:
    events = _events(saver, 1, regex=Raising("regex", RuntimeError("boom")))
    failed = [e for e in events if isinstance(e, NodeDone) and not e.ok]
    assert failed and failed[0].node == "extract_regex"
    assert failed[0].message and "boom" in failed[0].message
    assert isinstance(events[-1], Paused)  # escalated to a person, never approved


def test_elapsed_comes_from_the_injected_clock(saver: SqliteSaver) -> None:
    graph = build_graph(replay_deps(), checkpointer=saver)
    ticks = iter(range(0, 10_000, 5))
    events = list(stream_pack(graph, "supplier-pack-03", pack_path(3), clock=lambda: next(ticks)))
    elapsed = [e.elapsed_ms for e in events if isinstance(e, NodeDone)]
    assert elapsed == sorted(elapsed) and elapsed[0] > 0
