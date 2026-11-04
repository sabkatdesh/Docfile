from decimal import Decimal

from docgate.compare.arithmetic import ArithmeticFinding, check_arithmetic
from docgate.domain.config import DEFAULT_CONFIG
from docgate.domain.models import FieldStatus
from tests.factories import absent, baseline_extraction, ok

D = Decimal


def by_check(findings: list[ArithmeticFinding]) -> dict[str, bool | None]:
    return {f.check: f.ok for f in findings}


def test_baseline_all_ok() -> None:
    result = by_check(check_arithmetic(baseline_extraction(), DEFAULT_CONFIG))
    assert result == {"line_total": True, "vat": True, "total": True}


def test_pack01_numbers() -> None:
    ex = baseline_extraction(price="472.00", qty="12000")
    assert ex.subtotal.value == D("5664000.00")
    assert ex.vat_amount.value == D("849600.0000")
    assert by_check(check_arithmetic(ex, DEFAULT_CONFIG)) == {
        "line_total": True,
        "vat": True,
        "total": True,
    }


def test_line_total_wrong() -> None:
    ex = baseline_extraction(subtotal=ok(D("2000001.00"), "subtotal 2,000,001.00"))
    result = by_check(check_arithmetic(ex, DEFAULT_CONFIG))
    assert result["line_total"] is False


def test_vat_wrong_rate() -> None:
    sub = D("2000000.00")
    ex = baseline_extraction(vat_amount=ok(sub * D("0.10"), "VAT 10%"))
    assert by_check(check_arithmetic(ex, DEFAULT_CONFIG))["vat"] is False


def test_total_wrong() -> None:
    ex = baseline_extraction(total=ok(D("1.00"), "total 1.00"))
    assert by_check(check_arithmetic(ex, DEFAULT_CONFIG))["total"] is False


def test_tolerance_boundary() -> None:
    sub = D("2000000.00")
    vat = sub * D("0.15")
    near = baseline_extraction(total=ok(sub + vat + D("0.01"), "t"))
    far = baseline_extraction(total=ok(sub + vat + D("0.02"), "t"))
    assert by_check(check_arithmetic(near, DEFAULT_CONFIG))["total"] is True
    assert by_check(check_arithmetic(far, DEFAULT_CONFIG))["total"] is False


def test_inclusive_pack_checks_line_total_only() -> None:
    ex = baseline_extraction(
        price="94.00",
        qty="3000",
        vat_shown_separately=ok(False, "all taxes included"),
        subtotal=absent(),
        vat_amount=absent(),
        total=ok(D("282000.00"), "Total (all taxes included) 282,000.00"),
    )
    assert by_check(check_arithmetic(ex, DEFAULT_CONFIG)) == {"line_total": True}


def test_missing_subtotal_is_none() -> None:
    ex = baseline_extraction(subtotal=absent())
    result = by_check(check_arithmetic(ex, DEFAULT_CONFIG))
    assert result["line_total"] is None
    assert result["vat"] is None
    assert result["total"] is None


def test_vat_flag_unknown_all_none() -> None:
    ex = baseline_extraction(vat_shown_separately=absent(FieldStatus.UNVERIFIED))
    assert set(by_check(check_arithmetic(ex, DEFAULT_CONFIG)).values()) == {None}
