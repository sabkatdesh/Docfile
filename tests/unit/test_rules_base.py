import pytest

from docgate.domain.models import FieldStatus, RuleStatus
from docgate.rules.base import failed, passed, unknown, unknown_for_field
from tests.factories import absent, ok


def test_builders_set_status() -> None:
    assert passed("R1", "m", "q").status is RuleStatus.PASS
    assert failed("R1", "m", "q").status is RuleStatus.FAIL
    assert unknown("R1", "m").status is RuleStatus.UNKNOWN
    assert passed("R1", "m", "q").evidence_quote == "q"
    assert passed("R2", "m").rule_id == "R2"


@pytest.mark.parametrize(
    "status", [FieldStatus.MISSING, FieldStatus.UNVERIFIED, FieldStatus.CONFLICT]
)
def test_unknown_for_field_mentions_status(status: FieldStatus) -> None:
    r = unknown_for_field("R2", "advance payment", absent(status))
    assert r.status is RuleStatus.UNKNOWN
    assert status.value in r.message
    assert "advance payment" in r.message


def test_unknown_for_ok_field_is_a_bug() -> None:
    with pytest.raises(ValueError):
        unknown_for_field("R2", "x", ok(1))
