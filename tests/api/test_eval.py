"""GET /api/eval: golden vs actual, the confusion matrix and the precomputed mutation results."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from tests.api.conftest import GOLDEN, MUTATIONS, Built
from tests.api.test_review import P9, decide

Build = Callable[..., Built]


def test_golden_is_ten_of_ten_with_no_unsafe_errors(build: Build) -> None:
    body = build().client.get("/api/eval").json()
    g = body["golden"]
    assert (g["total"], g["correct"], g["passed"]) == (10, 10, True)
    assert g["unsafe"] == [] and g["conservative_misses"] == []
    expected = json.loads(GOLDEN.read_text("utf-8"))["expected"]
    assert {r["pack"]: r["expected"] for r in g["rows"]} == {int(k): v for k, v in expected.items()}
    assert all(r["match"] and r["expected"] == r["actual"] for r in g["rows"])
    labels = g["confusion"]["labels"]
    assert labels == ["Approve", "Reject", "Needs a person to check"]
    counts = g["confusion"]["counts"]
    assert [counts[i][i] for i in range(3)] == [2, 5, 3]
    assert sum(sum(row) for row in counts) == 10
    assert g["rows"][0]["pack_id"] == "supplier-pack-01"


def test_a_human_decision_shows_beside_the_score_but_never_changes_it(build: Build) -> None:
    b = build()
    before = b.client.get("/api/eval").json()["golden"]
    assert {r["human_decision"] for r in before["rows"]} == {None}
    b.run([9])
    assert decide(b, P9, decision="Approve", reason="checked by phone").status_code == 200
    after = b.client.get("/api/eval").json()["golden"]
    row = next(r for r in after["rows"] if r["pack"] == 9)
    assert row["human_decision"] == "Approve"
    assert row["actual"] == "Needs a person to check" and row["match"] is True
    assert (after["correct"], after["unsafe"]) == (10, [])


def test_mutation_results_come_from_the_committed_file(build: Build) -> None:
    m = build().client.get("/api/eval").json()["mutation"]
    assert m["available"] is True and m["reason"] is None
    assert m["total"] > 20 and m["passed"] == m["total"]
    families = {g["family"] for g in m["groups"]}
    assert {"mutation", "twin", "control", "stale"} <= families
    case = m["groups"][0]["cases"][0]
    assert {"id", "expect", "actual", "fired", "ok"} <= set(case)
    assert MUTATIONS.is_file()


def test_a_missing_mutation_file_is_reported_not_faked(build: Build, tmp_path: Path) -> None:
    m = build(mutation_file=tmp_path / "absent.json").client.get("/api/eval").json()["mutation"]
    assert m["available"] is False
    assert "mutation-report" in m["reason"]
    assert (m["total"], m["passed"], m["groups"]) == (0, 0, [])


def test_a_corrupt_mutation_file_is_reported_not_faked(build: Build, tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    m = build(mutation_file=bad).client.get("/api/eval").json()["mutation"]
    assert m["available"] is False and m["reason"]
