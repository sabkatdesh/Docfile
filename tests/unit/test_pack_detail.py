"""The pure view the API serves for one pack: findings in, a JSON-ready model out."""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from docgate.domain.models import Decision
from docgate.extraction.quotes import normalise
from docgate.review.checkpoint import sqlite_saver
from docgate.review.service import GraphReviewStore
from docgate.workflow.detail import build_detail, build_list_item
from docgate.workflow.graph import build_graph, run_pack
from tests.graph_support import pack_path, replay_deps


@pytest.fixture
def saver(tmp_path: Path) -> Iterator[SqliteSaver]:
    with sqlite_saver(tmp_path / "ck.sqlite") as s:
        yield s


def _state(saver: SqliteSaver, n: int) -> Any:
    graph = build_graph(replay_deps(), checkpointer=saver)
    return graph, run_pack(graph, f"supplier-pack-{n:02d}", pack_path(n))


def test_reject_pack_is_final_and_every_quote_has_a_span(saver: SqliteSaver) -> None:
    _, state = _state(saver, 3)
    d = build_detail(state)
    assert d.status == "final"
    assert d.machine.decision is Decision.REJECT
    assert d.machine.primary_rule == "R1"
    assert d.human_review is None
    quoted = [f for f in d.fields if f.quote]
    assert quoted
    for f in quoted:
        assert f.span is not None, f.name
        assert f.quote is not None
        assert normalise(d.text[f.span.start : f.span.end]) == normalise(f.quote)
    r1 = next(r for r in d.rules if r.rule_id == "R1")
    assert r1.status == "FAIL"
    assert r1.span is not None
    assert d.comparison is not None
    assert str(d.comparison.price_delta_pct) == "9.05"


def test_a_field_span_slices_back_to_its_quote(saver: SqliteSaver) -> None:
    _, state = _state(saver, 1)
    d = build_detail(state)
    price = next(f for f in d.fields if f.name == "unit_price")
    assert price.quote is not None and price.span is not None
    assert normalise(d.text[price.span.start : price.span.end]) == normalise(price.quote)


def test_approve_pack_has_only_passing_rules(saver: SqliteSaver) -> None:
    _, state = _state(saver, 1)
    d = build_detail(state)
    assert d.machine.decision is Decision.APPROVE
    assert d.status == "final"
    assert {r.status for r in d.rules} == {"PASS"}


def test_paused_pack_is_pending_with_its_findings(saver: SqliteSaver) -> None:
    _, state = _state(saver, 9)
    d = build_detail(state)
    assert d.status == "pending_review"
    assert d.machine.needs_human
    failing = {r.rule_id for r in d.rules if r.status != "PASS"}
    assert {"H3", "H6"} <= failing
    assert d.comparison is not None
    assert any(a.ok is False for a in d.comparison.arithmetic)


def test_resolved_pack_shows_the_human_decision_beside_the_machine_one(saver: SqliteSaver) -> None:
    graph, _ = _state(saver, 9)
    store = GraphReviewStore(
        graph, saver, clock=lambda: datetime.datetime(2026, 11, 6, tzinfo=datetime.UTC)
    )
    store.resolve("supplier-pack-09", Decision.REJECT, "arithmetic is wrong", "sam")
    resolved = store.state("supplier-pack-09")
    assert resolved is not None
    d = build_detail(resolved)
    assert d.status == "resolved"
    assert d.machine.decision is Decision.NEEDS_PERSON
    assert d.human_review is not None
    assert d.human_review.decision is Decision.REJECT
    assert d.human_review.reason == "arithmetic is wrong"


def test_store_state_is_none_for_a_pack_never_run(saver: SqliteSaver) -> None:
    graph, _ = _state(saver, 1)
    store = GraphReviewStore(graph, saver)
    assert store.state("supplier-pack-02") is None
    assert store.state("supplier-pack-01") is not None


def test_list_item_for_a_pack_not_run() -> None:
    item = build_list_item("supplier-pack-02", "supplier-pack-02.pdf", None)
    assert item.status == "not_run"
    assert item.decision is None and item.headline is None


def test_list_item_carries_supplier_and_item(saver: SqliteSaver) -> None:
    _, state = _state(saver, 3)
    item = build_list_item("supplier-pack-03", "supplier-pack-03.pdf", state)
    assert item.status == "final"
    assert item.decision is Decision.REJECT
    assert item.supplier and item.item
    assert item.primary_rule == "R1"
