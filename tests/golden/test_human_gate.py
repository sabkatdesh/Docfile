"""M4: Needs-person packs pause at the gate; every other pack runs straight through."""

from __future__ import annotations

import datetime
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from docgate.domain.models import Decision
from docgate.reporting.report import render_markdown
from docgate.review.checkpoint import sqlite_saver
from docgate.review.service import GraphReviewStore
from docgate.review.store import (
    AlreadyResolvedError,
    InvalidReviewError,
    NotReviewableError,
    ReviewKind,
    UnknownPackError,
)
from docgate.workflow.graph import build_graph, run_pack
from tests.graph_support import pack_path, replay_deps
from tests.unit.test_workflow import Raising


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("replay must never touch the network")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)


@pytest.fixture
def saver(tmp_path: Path) -> Iterator[SqliteSaver]:
    with sqlite_saver(tmp_path / "ck.sqlite") as s:
        yield s


def _run(saver: SqliteSaver, n: int) -> dict[str, Any]:
    graph = build_graph(replay_deps(), checkpointer=saver)
    return dict(run_pack(graph, f"supplier-pack-{n:02d}", pack_path(n)))


@pytest.mark.parametrize("n", [4, 7, 9])
def test_needs_person_packs_pause(saver: SqliteSaver, n: int) -> None:
    state = _run(saver, n)
    assert "__interrupt__" in state
    assert "report" not in state
    assert state["verdict"].decision is Decision.NEEDS_PERSON
    assert state["verdict"].human_decision is None
    payload = state["__interrupt__"][0].value
    assert payload["pack_id"] == f"supplier-pack-{n:02d}"
    assert payload["rules"]


@pytest.mark.parametrize("n", [1, 2, 3, 5, 6, 8, 10])
def test_other_packs_never_pause(saver: SqliteSaver, n: int) -> None:
    state = _run(saver, n)
    assert "__interrupt__" not in state
    assert state["report"].decision in (Decision.APPROVE, Decision.REJECT)
    assert state["report"].human_review is None


# --- the review store: list, show, resolve, restart --------------------------------------------

WHEN = datetime.datetime(2026, 11, 6, 9, 30, tzinfo=datetime.UTC)


def _store(saver: SqliteSaver) -> GraphReviewStore:
    graph = build_graph(replay_deps(), checkpointer=saver)
    return GraphReviewStore(graph, saver, clock=lambda: WHEN)


def _run_all(saver: SqliteSaver) -> None:
    for n in range(1, 11):
        _run(saver, n)


def test_pending_lists_exactly_the_paused_packs(saver: SqliteSaver) -> None:
    _run_all(saver)
    store = _store(saver)
    assert [p.pack_id for p in store.pending()] == [
        "supplier-pack-04",
        "supplier-pack-07",
        "supplier-pack-09",
    ]


def test_status_kinds(saver: SqliteSaver) -> None:
    _run_all(saver)
    store = _store(saver)
    assert store.status("supplier-pack-09").kind is ReviewKind.PENDING
    assert store.status("supplier-pack-01").kind is ReviewKind.NOT_REVIEWABLE
    assert store.status("supplier-pack-03").machine_decision is Decision.REJECT
    assert store.status("supplier-pack-99").kind is ReviewKind.UNKNOWN


def test_resume_after_a_process_restart(tmp_path: Path) -> None:
    db = tmp_path / "ck.sqlite"
    with sqlite_saver(db) as saver:
        _run(saver, 4)  # the first "process" pauses, then everything is dropped
    with sqlite_saver(db) as saver:  # a brand new connection, graph and store
        store = _store(saver)
        assert [p.pack_id for p in store.pending()] == ["supplier-pack-04"]
        final = store.resolve("supplier-pack-04", Decision.APPROVE, "Price within tolerance", "sab")
    assert "__interrupt__" not in final
    assert final["report"].human_review is not None


def test_pause_payload_survives_a_restart(tmp_path: Path) -> None:
    db = tmp_path / "ck.sqlite"
    with sqlite_saver(db) as saver:
        before = _run(saver, 9)["__interrupt__"][0].value
    with sqlite_saver(db) as saver:
        after = _store(saver).status("supplier-pack-09").payload
    assert after is not None and after.model_dump(mode="json") == before


@pytest.mark.parametrize(
    ("n", "decision"), [(4, Decision.APPROVE), (7, Decision.REJECT), (9, Decision.REJECT)]
)
def test_final_report_keeps_machine_verdict_and_human_decision(
    saver: SqliteSaver, n: int, decision: Decision
) -> None:
    _run(saver, n)
    pack = f"supplier-pack-{n:02d}"
    final = _store(saver).resolve(pack, decision, "Checked with the buyer", "sabkat")
    report = final["report"]
    assert report.decision is Decision.NEEDS_PERSON  # the machine verdict is untouched
    assert report.human_decision is decision
    review = report.human_review
    assert review is not None
    assert (review.reason, review.reviewer, review.reviewed_at) == (
        "Checked with the buyer",
        "sabkat",
        WHEN,
    )
    md = render_markdown(report)
    assert "Needs a person to check" in md
    assert decision.value in md and "Checked with the buyer" in md and "sabkat" in md


def test_resolve_twice_is_rejected_and_first_decision_kept(saver: SqliteSaver) -> None:
    _run(saver, 4)
    store = _store(saver)
    store.resolve("supplier-pack-04", Decision.APPROVE, "first", "alice")
    with pytest.raises(AlreadyResolvedError, match="alice"):
        store.resolve("supplier-pack-04", Decision.REJECT, "second", "bob")
    status = store.status("supplier-pack-04")
    assert status.kind is ReviewKind.RESOLVED
    assert status.human_review is not None
    assert (status.human_review.decision, status.human_review.reason) == (Decision.APPROVE, "first")


def test_unknown_pack_rejected(saver: SqliteSaver) -> None:
    with pytest.raises(UnknownPackError, match="supplier-pack-99"):
        _store(saver).resolve("supplier-pack-99", Decision.APPROVE, "x", "sab")


@pytest.mark.parametrize("reason", ["", "   "])
def test_empty_reason_rejected_and_pack_stays_pending(saver: SqliteSaver, reason: str) -> None:
    _run(saver, 7)
    store = _store(saver)
    with pytest.raises(InvalidReviewError, match="reason"):
        store.resolve("supplier-pack-07", Decision.APPROVE, reason, "sab")
    assert store.status("supplier-pack-07").kind is ReviewKind.PENDING


def test_needs_person_is_not_an_accepted_answer(saver: SqliteSaver) -> None:
    _run(saver, 7)
    with pytest.raises(InvalidReviewError, match="Approve or Reject"):
        _store(saver).resolve("supplier-pack-07", Decision.NEEDS_PERSON, "x", "sab")


@pytest.mark.parametrize("n", [1, 3])
def test_a_machine_final_pack_cannot_be_resolved(saver: SqliteSaver, n: int) -> None:
    _run(saver, n)
    with pytest.raises(NotReviewableError, match="final"):
        _store(saver).resolve(f"supplier-pack-{n:02d}", Decision.APPROVE, "override", "sab")


def test_escalated_pack_pauses_and_is_never_approved(saver: SqliteSaver) -> None:
    graph = build_graph(replay_deps(llm=Raising("llm", RuntimeError("boom"))), checkpointer=saver)
    # An Approve pack, but the LLM broke.
    state: dict[str, Any] = dict(run_pack(graph, "supplier-pack-01", pack_path(1)))
    assert "__interrupt__" in state
    assert state["verdict"].decision is Decision.NEEDS_PERSON
    payload = state["__interrupt__"][0].value
    assert payload["errors"] and "boom" in payload["errors"][0]["message"]
