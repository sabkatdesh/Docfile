from decimal import Decimal

import pytest
from pydantic import ValidationError

from docgate.domain.models import (
    Decision,
    Extraction,
    Field,
    FieldStatus,
    RuleResult,
    RuleStatus,
    Verdict,
)


def test_ok_field_needs_value_and_quote() -> None:
    f = Field[Decimal](value=Decimal("6.40"), quote="Unit price 6.40", status=FieldStatus.OK)
    assert f.value == Decimal("6.40")
    with pytest.raises(ValidationError):
        Field[Decimal](value=Decimal("6.40"), quote=None, status=FieldStatus.OK)
    with pytest.raises(ValidationError):
        Field[Decimal](value=None, quote="x", status=FieldStatus.OK)


@pytest.mark.parametrize(
    "status", [FieldStatus.MISSING, FieldStatus.UNVERIFIED, FieldStatus.CONFLICT]
)
def test_non_ok_field_never_carries_a_value(status: FieldStatus) -> None:
    Field[Decimal](value=None, quote=None, status=status)
    with pytest.raises(ValidationError):
        Field[Decimal](value=Decimal("1"), quote="q", status=status)


def test_field_rejects_float_value() -> None:
    with pytest.raises(ValidationError):
        Field[Decimal](value=6.4, quote="q", status=FieldStatus.OK)


def test_empty_extraction_is_all_missing() -> None:
    e = Extraction()
    assert e.unit_price.status is FieldStatus.MISSING
    assert e.tin.value is None
    assert e.payment_days.status is FieldStatus.MISSING


def test_rule_result_and_verdict() -> None:
    r = RuleResult(rule_id="R1", status=RuleStatus.UNKNOWN, message="no price")
    assert r.evidence_quote is None
    v = Verdict(decision=Decision.NEEDS_PERSON, reason="unknown price", rule_results=[r])
    assert v.needs_human is True
    assert v.human_decision is None


def test_approve_verdict_does_not_need_human() -> None:
    v = Verdict(decision=Decision.APPROVE, reason="all pass", rule_results=[])
    assert v.needs_human is False
