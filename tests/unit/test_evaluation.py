"""The eval must not lie: scoring is checked against hand-built wrong answers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from docgate.domain.models import Decision
from docgate.evaluation.golden import GoldenError, load_golden
from docgate.evaluation.score import render_report, score

A, R, N = Decision.APPROVE, Decision.REJECT, Decision.NEEDS_PERSON
GOLDEN_FILE = Path(__file__).parents[2] / "data" / "golden" / "expected.json"
EXPECTED = {1: A, 2: R, 3: N}


def test_all_correct() -> None:
    result = score(EXPECTED, dict(EXPECTED))
    assert (result.correct, result.total, result.unsafe) == (3, 3, [])
    assert result.passed


def test_wrong_approve_is_unsafe() -> None:
    result = score(EXPECTED, {1: A, 2: A, 3: N})  # pack 2 should be Reject
    assert result.unsafe == [2]
    assert result.correct == 2
    assert not result.passed


def test_wrong_approve_on_needs_person_is_unsafe() -> None:
    assert score(EXPECTED, {1: A, 2: R, 3: A}).unsafe == [3]


def test_wrong_reject_is_a_mismatch_but_not_unsafe() -> None:
    result = score(EXPECTED, {1: R, 2: R, 3: N})
    assert result.unsafe == []
    assert result.correct == 2
    assert not result.passed


def test_missing_actual_is_a_mismatch_never_a_pass() -> None:
    result = score(EXPECTED, {1: A, 2: R})
    assert result.correct == 2
    assert not result.passed
    assert result.rows[-1].actual is None


def test_extra_actual_pack_is_a_failure() -> None:
    assert not score(EXPECTED, {**EXPECTED, 4: A}).passed


def test_conservative_miss_counted_separately() -> None:
    result = score(EXPECTED, {1: A, 2: N, 3: N})  # Reject expected, person asked
    assert result.conservative_misses == [2]
    assert result.unsafe == []


def test_confusion_matrix_counts() -> None:
    result = score(EXPECTED, {1: A, 2: A, 3: N})
    assert result.confusion[(R, A)] == 1
    assert result.confusion[(A, A)] == 1
    assert result.confusion[(N, N)] == 1
    assert result.confusion[(R, R)] == 0


def test_report_shows_counts_and_matrix() -> None:
    text = render_report(score(EXPECTED, {1: A, 2: A, 3: N}))
    assert "accuracy: 2/3" in text
    assert "unsafe errors: 1" in text
    assert "MISMATCH" in text


def test_real_golden_file_matches_the_spec_table() -> None:
    golden = load_golden(GOLDEN_FILE)
    assert golden == {1: A, 2: A, 3: R, 4: N, 5: R, 6: R, 7: N, 8: R, 9: N, 10: R}


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps({"expected": {"1": "Maybe"}}),
        json.dumps({"expected": {"x": "Approve"}}),
        json.dumps({"nope": {}}),
        json.dumps({"expected": {}}),
    ],
)
def test_bad_golden_file_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "g.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(GoldenError):
        load_golden(path)
