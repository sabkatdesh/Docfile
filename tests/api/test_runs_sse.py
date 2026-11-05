"""Starting runs and reading their progress over SSE."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from docgate.extraction.base import ExtractorOutput
from tests.api.conftest import Built, parse_sse
from tests.api.test_basics import error_of
from tests.graph_support import replay_deps

Build = Callable[..., Built]


class Gate:
    name = "llm"

    def __init__(self) -> None:
        self.inner = replay_deps().llm
        self.entered = threading.Event()
        self.release = threading.Event()

    def extract(self, text: str, label: str = "") -> ExtractorOutput:
        self.entered.set()
        assert self.release.wait(10)
        return self.inner.extract(text, label)


def test_post_runs_is_accepted_and_names_its_stream(build: Build) -> None:
    b = build()
    res = b.client.post("/api/runs", json={"packs": [1]})
    assert res.status_code == 202
    body = res.json()
    assert body["packs"] == ["supplier-pack-01"]
    assert body["events_url"] == f"/api/runs/{body['run_id']}/events"
    b.client.get(body["events_url"])


def test_the_stream_is_ordered_and_ends_with_run_finished(build: Build) -> None:
    b = build()
    res = b.client.post("/api/runs", json={"packs": [3, 9]})
    with b.client.stream("GET", res.json()["events_url"]) as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert stream.headers["cache-control"] == "no-cache"
        frames = parse_sse("".join(stream.iter_text()))
    kinds = [f["event"] for f in frames]
    assert kinds[0] == "run_started" and kinds[-1] == "run_finished"
    assert [f["id"] for f in frames] == list(range(1, len(frames) + 1))
    assert kinds.count("pack_started") == 2
    assert kinds.count("pack_finished") == 1 and kinds.count("pack_paused") == 1
    first = kinds.index("pack_started")
    assert kinds[first + 1] == "node_completed"
    assert frames[first]["data"]["pack_id"] == "supplier-pack-03"
    assert frames[first]["data"]["steps"][0] == "ingest"
    assert all(f["data"]["run_id"] == res.json()["run_id"] for f in frames)
    assert frames[-1]["data"]["paused"] == ["supplier-pack-09"]
    assert "error" not in kinds


def test_last_event_id_replays_only_the_tail(build: Build) -> None:
    b = build()
    run_id = b.run([3])
    url = f"/api/runs/{run_id}/events"
    everything = parse_sse(b.client.get(url).text)
    tail = parse_sse(b.client.get(url, headers={"Last-Event-ID": "5"}).text)
    assert [f["id"] for f in tail] == [f["id"] for f in everything if f["id"] > 5]
    junk = parse_sse(b.client.get(url, headers={"Last-Event-ID": "abc"}).text)
    assert len(junk) == len(everything)  # an unreadable id means "from the start"


def test_unknown_run_is_404(build: Build) -> None:
    res = build().client.get("/api/runs/nope/events")
    assert res.status_code == 404 and error_of(res)["code"] == "unknown_run"


def test_full_run_through_the_api_matches_the_golden_split(build: Build) -> None:
    b = build()
    run_id = b.run(None)
    frames = parse_sse(b.client.get(f"/api/runs/{run_id}/events").text)
    done = frames[-1]["data"]
    assert done["status"] == "completed"
    assert done["counts"] == {"Approve": 2, "Reject": 5, "Needs a person to check": 3}
    assert len(done["finished"]) == 7
    assert done["paused"] == ["supplier-pack-04", "supplier-pack-07", "supplier-pack-09"]


def test_unknown_pack_number_and_bad_body(build: Build) -> None:
    b = build()
    res = b.client.post("/api/runs", json={"packs": [1, 99]})
    assert res.status_code == 404 and error_of(res)["code"] == "unknown_pack_number"
    res = b.client.post("/api/runs", json={"packs": "all"})
    assert res.status_code == 422 and error_of(res)["code"] == "validation_error"
    res = b.client.post("/api/runs", content="packs=1", headers={"Content-Type": "text/plain"})
    assert res.status_code == 422
    assert b.manager.active_run_id is None


def test_a_second_run_while_one_is_active_is_409(build: Build) -> None:
    gate = Gate()
    b = build(replay_deps(llm=gate))
    first = b.client.post("/api/runs", json={"packs": [1]})
    assert gate.entered.wait(10)
    assert b.client.get("/api/health").json()["active_run_id"] == first.json()["run_id"]
    res = b.client.post("/api/runs", json={"packs": [2]})
    assert res.status_code == 409
    err = error_of(res)
    assert err["code"] == "run_in_progress"
    assert err["details"]["run_id"] == first.json()["run_id"]
    gate.release.set()
    b.client.get(first.json()["events_url"])
    again = b.client.post("/api/runs", json={"packs": [2]})
    assert again.status_code == 202
    b.client.get(again.json()["events_url"])


def test_fresh_run_with_pending_reviews_is_refused_until_discard_is_explicit(build: Build) -> None:
    b = build()
    b.run([9])
    res = b.client.post("/api/runs", json={"packs": [1]})
    assert res.status_code == 409
    err = error_of(res)
    assert err["code"] == "pending_reviews_would_be_lost"
    assert err["details"]["pack_ids"] == ["supplier-pack-09"]
    assert [r["pack_id"] for r in b.client.get("/api/review").json()] == ["supplier-pack-09"]
    b.run([1], discard_pending=True)
    assert b.client.get("/api/review").json() == []


def test_resume_keeps_the_record_and_skips_what_is_on_it(build: Build) -> None:
    b = build()
    b.run([9])
    run_id = b.run([9, 1], resume=True)
    kinds: list[Any] = [
        f["event"] for f in parse_sse(b.client.get(f"/api/runs/{run_id}/events").text)
    ]
    assert "pack_skipped" in kinds
    assert [r["pack_id"] for r in b.client.get("/api/review").json()] == ["supplier-pack-09"]
