from __future__ import annotations

from decimal import Decimal

from docgate.domain.models import Extraction, FieldStatus
from docgate.extraction.base import Candidate, ExtractorOutput, absent, found, unreadable
from docgate.extraction.reconcile import reconcile

TEXT = "Unit price 6.65 piece. Late delivery penalty of 0.6% of order value per week."
PRICE_QUOTE = "Unit price 6.65"


def _out(source: str, **cands: Candidate) -> ExtractorOutput:
    return ExtractorOutput(source=source, candidates=cands)


def _price(llm: Candidate, rx: Candidate) -> tuple[FieldStatus, Extraction]:
    result = reconcile(_out("llm", unit_price=llm), _out("regex", unit_price=rx), TEXT)
    return result.extraction.unit_price.status, result.extraction


def _good(value: str = "6.65") -> Candidate:
    return found(Decimal(value), PRICE_QUOTE, raw="6.65")


def test_agree_is_ok_with_the_llm_quote() -> None:
    status, ex = _price(_good(), found(Decimal("6.650"), "Unit price 6.65 piece", raw="6.65"))
    assert status is FieldStatus.OK
    assert ex.unit_price.value == Decimal("6.65")
    assert ex.unit_price.quote == PRICE_QUOTE


def test_disagree_is_conflict_and_keeps_both_values_in_issues() -> None:
    result = reconcile(
        _out("llm", unit_price=_good()),
        _out("regex", unit_price=found(Decimal("6.56"), "Unit price 6.65", raw="6.65")),
        TEXT,
    )
    assert result.extraction.unit_price.status is FieldStatus.CONFLICT
    assert result.extraction.unit_price.value is None
    (issue,) = [i for i in result.issues if i.field == "unit_price"]
    assert issue.status is FieldStatus.CONFLICT
    assert issue.llm_value == Decimal("6.65")
    assert issue.regex_value == Decimal("6.56")


def test_both_absent_is_missing() -> None:
    status, _ = _price(absent(), absent())
    assert status is FieldStatus.MISSING


def test_llm_found_regex_absent_is_conflict() -> None:
    assert _price(_good(), absent())[0] is FieldStatus.CONFLICT


def test_llm_null_regex_found_is_conflict() -> None:
    assert _price(absent(), _good())[0] is FieldStatus.CONFLICT


def test_regex_unreadable_is_unverified() -> None:
    assert _price(_good(), unreadable("pattern failed"))[0] is FieldStatus.UNVERIFIED


def test_llm_null_regex_unreadable_is_unverified() -> None:
    assert _price(absent(), unreadable("two matches"))[0] is FieldStatus.UNVERIFIED


def test_llm_quote_not_in_text_is_unverified_even_if_regex_agrees() -> None:
    bad = found(Decimal("6.65"), "Unit price 7.77 piece", raw="6.65")
    assert _price(bad, _good())[0] is FieldStatus.UNVERIFIED


def test_llm_bad_quote_with_regex_absent_is_unverified_not_missing() -> None:
    bad = found(Decimal("6.65"), "invented quote", raw="6.65")
    assert _price(bad, absent())[0] is FieldStatus.UNVERIFIED


def test_field_missing_from_both_outputs_is_unverified() -> None:
    result = reconcile(_out("llm"), _out("regex"), TEXT)
    assert result.extraction.qty.status is FieldStatus.UNVERIFIED


def test_llm_failure_makes_every_field_unverified_never_missing() -> None:
    failed = ExtractorOutput(source="llm", failure="timeout after 4 attempts")
    rx = _out("regex", unit_price=_good(), tin=absent())
    result = reconcile(failed, rx, TEXT)
    for name in Extraction.model_fields:
        assert getattr(result.extraction, name).status is FieldStatus.UNVERIFIED, name
    assert any("timeout" in i.reason for i in result.issues)


def test_string_values_compare_ignoring_case_and_spacing() -> None:
    llm = found("Padma  Textile Ltd", "Padma Textile Ltd", raw="Padma Textile Ltd")
    rx = found("padma textile ltd", "Padma Textile Ltd", raw="Padma Textile Ltd")
    result = reconcile(_out("llm", supplier=llm), _out("regex", supplier=rx), "Padma Textile Ltd")
    assert result.extraction.supplier.status is FieldStatus.OK


def test_ok_fields_always_hold_a_verified_quote() -> None:
    result = reconcile(_out("llm", unit_price=_good()), _out("regex", unit_price=_good()), TEXT)
    assert result.extraction.unit_price.quote is not None
