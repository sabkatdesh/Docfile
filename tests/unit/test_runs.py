"""The run lifecycle without HTTP: one background run, an ordered event log, a fresh-or-resume
database policy and a lock that keeps a review from racing a run."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from docgate.domain.models import Decision
from docgate.extraction.base import Extractor, ExtractorOutput
from docgate.llm.provider import LLMConfigError
from docgate.workflow.deps import Deps
from docgate.workflow.runs import (
    PendingReviewsError,
    RunEvent,
    RunInProgressError,
    RunManager,
    UnknownPackNumberError,
    UnknownRunError,
)
from tests.graph_support import pack_path, replay_deps
from tests.unit.test_workflow import Raising

PACKS = {f"supplier-pack-{n:02d}": pack_path(n) for n in range(1, 11)}


class Gate:
    """Wraps the real extractor and holds every pack at the extraction step until released."""

    name = "llm"

    def __init__(self, inner: Extractor) -> None:
        self.inner = inner
        self.entered = threading.Event()
        self.release = threading.Event()

    def extract(self, text: str, label: str = "") -> ExtractorOutput:
        self.entered.set()
        assert self.release.wait(10), "test gate never released"
        return self.inner.extract(text, label)


@pytest.fixture
def make(tmp_path: Path) -> Iterator[Any]:
    managers: list[RunManager] = []

    def factory(deps: Deps | None = None, db: str = "api.sqlite") -> RunManager:
        m = RunManager(deps or replay_deps(), PACKS, tmp_path / db, out_dir=tmp_path / "reports")
        managers.append(m)
        return m

    yield factory
    for m in managers:
        m.close()


def drain(m: RunManager, run_id: str) -> list[RunEvent]:
    events: list[RunEvent] = []
    while True:
        batch, finished = m.events_after(run_id, len(events), timeout=10)
        events += batch
        if finished:
            return events


def types(events: list[RunEvent]) -> list[str]:
    return [e.type for e in events]


def test_single_pack_run_emits_the_ordered_events(make: Any) -> None:
    m = make()
    run = m.start([1])
    events = drain(m, run.run_id)
    assert types(events)[:2] == ["run_started", "pack_started"]
    assert types(events)[-2:] == ["pack_finished", "run_finished"]
    assert types(events).count("node_completed") == 8
    assert [e.seq for e in events] == list(range(1, len(events) + 1))
    assert events[0].data["packs"] == ["supplier-pack-01"]
    assert events[1].data["steps"][0] == "ingest"
    done = events[-1].data
    assert done["status"] == "completed"
    assert done["counts"] == {"Approve": 1}


def test_full_run_matches_the_golden_split(make: Any) -> None:
    m = make()
    events = drain(m, m.start(None).run_id)
    done = events[-1].data
    assert len(done["finished"]) == 7
    assert done["paused"] == ["supplier-pack-04", "supplier-pack-07", "supplier-pack-09"]
    assert done["counts"] == {"Approve": 2, "Reject": 5, "Needs a person to check": 3}
    paused = [e for e in events if e.type == "pack_paused"]
    assert [e.data["pack_id"] for e in paused] == done["paused"]
    assert all(e.data["machine_decision"] == Decision.NEEDS_PERSON.value for e in paused)
    finished = {e.data["pack_id"]: e.data for e in events if e.type == "pack_finished"}
    assert finished["supplier-pack-03"]["decision"] == "Reject"
    assert finished["supplier-pack-03"]["primary_rule"] == "R1"


def test_events_after_replays_only_the_tail(make: Any) -> None:
    m = make()
    run = m.start([3])
    events = drain(m, run.run_id)
    tail, finished = m.events_after(run.run_id, 3, timeout=1)
    assert finished and [e.seq for e in tail] == [e.seq for e in events[3:]]


def test_unknown_run_and_unknown_pack_number(make: Any) -> None:
    m = make()
    with pytest.raises(UnknownRunError):
        m.events_after("nope", 0, timeout=0.1)
    with pytest.raises(UnknownPackNumberError, match="99"):
        m.start([1, 99])
    assert m.active_run_id is None  # a refused request starts nothing


def test_only_one_run_at_a_time(make: Any) -> None:
    gate = Gate(replay_deps().llm)
    m = make(replay_deps(llm=gate))
    first = m.start([1])
    assert gate.entered.wait(10)
    assert m.active_run_id == first.run_id
    with pytest.raises(RunInProgressError) as err:
        m.start([2])
    assert err.value.run_id == first.run_id
    gate.release.set()
    drain(m, first.run_id)
    assert m.active_run_id is None
    drain(m, m.start([2]).run_id)  # free again


def test_review_is_refused_while_a_run_is_active(make: Any) -> None:
    m = make()
    drain(m, m.start([9]).run_id)
    gate = Gate(replay_deps().llm)
    busy = make(replay_deps(llm=gate), db="other.sqlite")
    run = busy.start([1])
    assert gate.entered.wait(10)
    with pytest.raises(RunInProgressError):
        busy.resolve("supplier-pack-09", Decision.REJECT, "why", "sam")
    gate.release.set()
    drain(busy, run.run_id)
    m.resolve("supplier-pack-09", Decision.REJECT, "arithmetic is wrong", "sam")
    assert (m.out_dir / "summary.json").is_file()  # the audit files follow a decision


def test_fresh_run_refuses_to_discard_pending_reviews(make: Any) -> None:
    m = make()
    drain(m, m.start(None).run_id)
    with pytest.raises(PendingReviewsError) as err:
        m.start([1])
    assert err.value.pack_ids == ["supplier-pack-04", "supplier-pack-07", "supplier-pack-09"]
    assert len(m.pending()) == 3  # untouched
    assert len(m.states()) == 10


def test_discard_pending_wipes_the_old_record(make: Any) -> None:
    m = make()
    drain(m, m.start(None).run_id)
    drain(m, m.start([1], discard_pending=True).run_id)
    assert [s["pack_id"] for s in m.states()] == ["supplier-pack-01"]
    assert m.pending() == []


def test_fresh_run_after_all_reviews_are_resolved_is_allowed(make: Any) -> None:
    m = make()
    drain(m, m.start([9]).run_id)
    m.resolve("supplier-pack-09", Decision.REJECT, "arithmetic is wrong", "sam")
    drain(m, m.start([1]).run_id)
    assert [s["pack_id"] for s in m.states()] == ["supplier-pack-01"]


def test_resume_keeps_the_record_and_skips_packs_on_record(make: Any) -> None:
    m = make()
    drain(m, m.start([9]).run_id)
    events = drain(m, m.start([9, 1], resume=True).run_id)
    skipped = [e for e in events if e.type == "pack_skipped"]
    assert [e.data["pack_id"] for e in skipped] == ["supplier-pack-09"]
    assert len(m.pending()) == 1  # still waiting; the re-run did not restart it
    assert {s["pack_id"] for s in m.states()} == {"supplier-pack-01", "supplier-pack-09"}


def test_a_config_error_stops_the_run_with_error_then_run_finished(make: Any) -> None:
    m = make(replay_deps(llm=Raising("llm", LLMConfigError("GROQ_API_KEY is wrong"))))
    events = drain(m, m.start([1, 2]).run_id)
    assert types(events)[-2:] == ["error", "run_finished"]
    assert events[-2].data["fatal"] is True
    assert "GROQ_API_KEY is wrong" in events[-2].data["message"]
    assert events[-1].data["status"] == "failed"
    assert "pack_started" in types(events)
    assert [e.data["pack_id"] for e in events if e.type == "pack_started"] == ["supplier-pack-01"]


def test_a_node_failure_escalates_that_pack_and_the_run_goes_on(make: Any) -> None:
    m = make(replay_deps(regex=Raising("regex", RuntimeError("boom"))))
    events = drain(m, m.start([1, 3]).run_id)
    bad = [e for e in events if e.type == "node_completed" and not e.data["ok"]]
    assert bad and "boom" in bad[0].data["message"]
    assert "error" not in types(events)
    assert events[-1].data["status"] == "completed"
    assert events[-1].data["counts"] == {"Needs a person to check": 2}  # never Approve


def test_a_second_manager_on_the_same_file_sees_the_record(make: Any, tmp_path: Path) -> None:
    first = make()
    drain(first, first.start([9]).run_id)
    first.close()
    again = make()
    assert [p.pack_id for p in again.pending()] == ["supplier-pack-09"]
