"""A human review is only valid with Approve or Reject and a real reason."""

from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from docgate.domain.models import Decision, HumanReview, Verdict

WHEN = datetime.datetime(2026, 11, 6, 9, 30, tzinfo=datetime.UTC)


def _review(**changes: object) -> HumanReview:
    base: dict[str, object] = {
        "decision": Decision.APPROVE,
        "reason": "Supplier confirmed by phone",
        "reviewer": "sabkat",
        "reviewed_at": WHEN,
    }
    return HumanReview.model_validate({**base, **changes})


def test_valid_review_keeps_every_field() -> None:
    r = _review()
    assert (r.decision, r.reason, r.reviewer, r.reviewed_at) == (
        Decision.APPROVE,
        "Supplier confirmed by phone",
        "sabkat",
        WHEN,
    )


@pytest.mark.parametrize("reason", ["", "   ", "\n\t"])
def test_blank_reason_rejected(reason: str) -> None:
    with pytest.raises(ValidationError, match="reason"):
        _review(reason=reason)


@pytest.mark.parametrize("reviewer", ["", "  "])
def test_blank_reviewer_rejected(reviewer: str) -> None:
    with pytest.raises(ValidationError, match="reviewer"):
        _review(reviewer=reviewer)


def test_needs_person_is_not_a_valid_human_decision() -> None:
    with pytest.raises(ValidationError, match="Approve or Reject"):
        _review(decision=Decision.NEEDS_PERSON)


def test_reason_is_stored_stripped() -> None:
    assert _review(reason="  ok  ").reason == "ok"


def test_naive_timestamp_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        _review(reviewed_at=datetime.datetime(2026, 11, 6, 9, 30))


def test_verdict_exposes_the_human_decision_from_the_review() -> None:
    v = Verdict(decision=Decision.NEEDS_PERSON, reason="r", rule_results=[], human_review=_review())
    assert v.human_decision is Decision.APPROVE
    assert v.decision is Decision.NEEDS_PERSON  # the machine verdict is never overwritten
