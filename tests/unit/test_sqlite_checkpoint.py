"""M4 step 1: the full pack state must survive a SQLite checkpoint and a reconnect."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from docgate.domain.models import Decision
from docgate.review.checkpoint import sqlite_saver
from docgate.review.service import GraphReviewStore
from docgate.workflow.graph import build_graph, run_pack
from tests.graph_support import pack_path, replay_deps

CONFIG = {"configurable": {"thread_id": "supplier-pack-04"}}


def test_state_survives_a_sqlite_reconnect(tmp_path: Path) -> None:
    db = tmp_path / "ck.sqlite"
    with sqlite_saver(db) as saver:
        run_pack(
            build_graph(replay_deps(), checkpointer=saver),
            "supplier-pack-04",
            pack_path(4),
            config=CONFIG,
        )
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # an unregistered-type warning means a future break
        with sqlite_saver(db) as saver:
            saved = build_graph(replay_deps(), checkpointer=saver).get_state(CONFIG).values
    assert saved["verdict"].decision is Decision.NEEDS_PERSON
    assert str(saved["extraction"].unit_price.value) == "6.65"
    assert str(saved["comparison"].price_delta_pct).startswith("2.30")


def test_reading_a_checkpoint_raises_no_unregistered_type_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """LangGraph will block unregistered types in a future version; our types must be listed."""
    db = tmp_path / "ck.sqlite"
    with sqlite_saver(db) as saver:
        graph = build_graph(replay_deps(), checkpointer=saver)
        for n in (1, 3, 4, 9):
            run_pack(graph, f"supplier-pack-{n:02d}", pack_path(n))
        store = GraphReviewStore(graph, saver)
        store.resolve("supplier-pack-04", Decision.APPROVE, "ok", "sab")
    with sqlite_saver(db) as saver:
        store = GraphReviewStore(build_graph(replay_deps(), checkpointer=saver), saver)
        assert len(store.states()) == 4
        store.status("supplier-pack-09")
    assert [r.message for r in caplog.records if "unregistered" in r.message] == []
