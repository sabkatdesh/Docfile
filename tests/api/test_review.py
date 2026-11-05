"""The review queue and every way a resolve can be refused."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tests.api.conftest import Built
from tests.api.test_basics import error_of
from tests.api.test_runs_sse import Gate
from tests.graph_support import replay_deps

Build = Callable[..., Built]
P9 = "/api/review/supplier-pack-09"


def decide(b: Built, url: str = P9, **body: Any) -> Any:
    payload = {"decision": "Reject", "reason": "arithmetic is wrong", "reviewer": "sam", **body}
    return b.client.post(url, json=payload)


def test_queue_lists_the_three_paused_packs_with_their_evidence(build: Build) -> None:
    b = build()
    b.run(None)
    items = b.client.get("/api/review").json()
    assert [i["pack_id"] for i in items] == [
        "supplier-pack-04",
        "supplier-pack-07",
        "supplier-pack-09",
    ]
    payload = items[2]["payload"]
    assert payload["machine_decision"] == "Needs a person to check"
    assert {"H3", "H6"} <= {r["rule_id"] for r in payload["rules"]}
    assert payload["question"]


def test_resolve_records_the_human_decision_beside_the_machine_one(build: Build) -> None:
    b = build()
    b.run([9])
    res = decide(b)
    assert res.status_code == 200
    row = res.json()
    assert row["status"] == "resolved"
    assert row["decision"] == "Needs a person to check"  # the machine verdict is not overwritten
    assert row["human_decision"] == "Reject"
    detail = b.client.get("/api/packs/supplier-pack-09").json()
    assert detail["human_review"]["reason"] == "arithmetic is wrong"
    assert detail["human_review"]["reviewer"] == "sam"
    assert b.client.get("/api/review").json() == []


def test_reviewer_defaults_to_the_configured_name(build: Build) -> None:
    b = build(default_reviewer="the-operator")
    b.run([9])
    res = b.client.post(P9, json={"decision": "Approve", "reason": "checked with the supplier"})
    assert res.status_code == 200
    detail = b.client.get("/api/packs/supplier-pack-09").json()
    assert detail["human_review"]["reviewer"] == "the-operator"


def test_resolving_twice_keeps_the_first_decision(build: Build) -> None:
    b = build()
    b.run([9])
    assert decide(b).status_code == 200
    res = decide(b, decision="Approve", reason="changed my mind")
    assert res.status_code == 409 and error_of(res)["code"] == "already_resolved"
    assert (
        b.client.get("/api/packs/supplier-pack-09").json()["human_review"]["decision"] == "Reject"
    )


def test_blank_reason_is_422_and_changes_nothing(build: Build) -> None:
    b = build()
    b.run([9])
    for reason in ("", "   ", "\n\t"):
        res = decide(b, reason=reason)
        assert res.status_code == 422 and error_of(res)["code"] == "invalid_review"
    assert len(b.client.get("/api/review").json()) == 1


def test_a_human_cannot_answer_needs_a_person(build: Build) -> None:
    b = build()
    b.run([9])
    res = decide(b, decision="Needs a person to check")
    assert res.status_code == 422 and error_of(res)["code"] == "invalid_review"


def test_machine_final_packs_are_not_reviewable(build: Build) -> None:
    b = build()
    b.run([1, 3])
    for pack in ("supplier-pack-01", "supplier-pack-03"):
        res = decide(b, f"/api/review/{pack}")
        assert res.status_code == 409 and error_of(res)["code"] == "machine_final"


def test_unknown_and_never_run_packs_are_404(build: Build) -> None:
    b = build()
    b.run([9])
    for pack in ("supplier-pack-99", "supplier-pack-02", "..%2fetc"):
        res = decide(b, f"/api/review/{pack}")
        # A traversal string matches no route at all (the catch-all only answers GET).
        assert res.status_code in {404, 405}, pack
        assert error_of(res)["code"] in {"unknown_pack", "not_found", "method_not_allowed"}


def test_malformed_body_is_a_validation_error(build: Build) -> None:
    b = build()
    b.run([9])
    for body in ({"reason": "x"}, {"decision": "Maybe", "reason": "x"}, {"decision": "Reject"}):
        res = b.client.post(P9, json=body)
        assert res.status_code == 422 and error_of(res)["code"] == "validation_error"
    assert len(b.client.get("/api/review").json()) == 1


def test_resolving_during_a_run_is_refused(build: Build) -> None:
    gate = Gate()
    b = build(replay_deps(llm=gate))
    gate.release.set()
    b.run([9])
    gate.release.clear()
    gate.entered.clear()
    res = b.client.post("/api/runs", json={"packs": [1], "resume": True})
    assert res.status_code == 202
    assert gate.entered.wait(10)
    refused = decide(b)
    assert refused.status_code == 409 and error_of(refused)["code"] == "run_in_progress"
    gate.release.set()
    b.client.get(res.json()["events_url"])
    assert decide(b).status_code == 200
