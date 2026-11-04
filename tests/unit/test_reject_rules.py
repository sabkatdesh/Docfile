from decimal import Decimal

from docgate.domain.config import DEFAULT_CONFIG
from docgate.domain.models import Field, FieldStatus, RuleStatus
from docgate.rules.reject import (
    r1_price,
    r2_advance,
    r3_penalty,
    r4_tax_ids,
    r5_delivery,
)
from tests.factories import absent, baseline_extraction, ok, pr_line

D = Decimal
P, F, U = RuleStatus.PASS, RuleStatus.FAIL, RuleStatus.UNKNOWN
CFG = DEFAULT_CONFIG


def r1(price: str, max_price: str = "100.00") -> RuleStatus:
    return r1_price(baseline_extraction(price=price), pr_line(max_price=max_price), CFG).status


def test_r1_boundaries() -> None:
    assert r1("100.00") is P
    assert r1("99.00") is P
    assert r1("103.00") is P  # exactly +3% is H1, not R1
    assert r1("103.01") is F
    assert r1("39.14", max_price="38") is P
    assert r1("39.15", max_price="38") is F


def test_r1_unknown_cases() -> None:
    pr = pr_line()
    for status in (FieldStatus.MISSING, FieldStatus.UNVERIFIED, FieldStatus.CONFLICT):
        ex = baseline_extraction(unit_price=absent(status))
        assert r1_price(ex, pr, CFG).status is U
    assert r1_price(baseline_extraction(unit_price=ok(D("0"))), pr, CFG).status is U
    assert r1_price(baseline_extraction(unit_price=ok(D("-5"))), pr, CFG).status is U
    assert r1_price(baseline_extraction(), None, CFG).status is U
    assert r1_price(baseline_extraction(unit=ok("dozen")), pr, CFG).status is U
    inclusive = baseline_extraction(vat_shown_separately=ok(False, "taxes included"))
    assert r1_price(inclusive, pr, CFG).status is U


def r2(v: str) -> RuleStatus:
    ex = baseline_extraction(advance_pct=ok(D(v), f"{v}% advance"))
    return r2_advance(ex, pr_line(), CFG).status


def test_r2() -> None:
    assert r2("20") is P
    assert r2("20.1") is F
    assert r2("0") is P
    assert r2("40") is F
    assert r2("101") is U
    assert r2("-1") is U
    assert r2_advance(baseline_extraction(advance_pct=absent()), pr_line(), CFG).status is U


def r3(v: str) -> RuleStatus:
    ex = baseline_extraction(penalty_pct_per_week=ok(D(v), f"{v}% per week"))
    return r3_penalty(ex, pr_line(), CFG).status


def test_r3() -> None:
    assert r3("0.5") is P
    assert r3("0.49") is F
    assert r3("1") is P
    assert r3("-1") is U
    missing = r3_penalty(baseline_extraction(penalty_pct_per_week=absent()), pr_line(), CFG)
    assert missing.status is F
    assert "no late-delivery penalty clause" in missing.message
    for status in (FieldStatus.UNVERIFIED, FieldStatus.CONFLICT):
        ex = baseline_extraction(penalty_pct_per_week=absent(status))
        assert r3_penalty(ex, pr_line(), CFG).status is U


def test_r4() -> None:
    pr = pr_line()
    assert r4_tax_ids(baseline_extraction(), pr, CFG).status is P
    assert r4_tax_ids(baseline_extraction(tin=absent()), pr, CFG).status is F
    assert r4_tax_ids(baseline_extraction(bin=absent()), pr, CFG).status is F
    assert r4_tax_ids(baseline_extraction(tin=absent(), bin=absent()), pr, CFG).status is F
    unv: Field[str] = absent(FieldStatus.UNVERIFIED)
    con: Field[str] = absent(FieldStatus.CONFLICT)
    assert r4_tax_ids(baseline_extraction(tin=unv), pr, CFG).status is U
    assert r4_tax_ids(baseline_extraction(tin=con), pr, CFG).status is U
    # An ID that is genuinely absent is a Reject even if the other one is unreadable.
    assert r4_tax_ids(baseline_extraction(tin=absent(), bin=con), pr, CFG).status is F


def r5(days: int) -> RuleStatus:
    ex = baseline_extraction(delivery_days=ok(days, f"within {days} days"))
    return r5_delivery(ex, pr_line(), CFG).status


def test_r5() -> None:
    assert r5(45) is P
    assert r5(46) is F
    assert r5(44) is P
    assert r5(60) is F
    assert r5(0) is U
    assert r5_delivery(baseline_extraction(delivery_days=absent()), pr_line(), CFG).status is U


def test_fail_results_carry_the_quote() -> None:
    ex = baseline_extraction(
        unit_price=ok(D("104"), "104.00"),
        advance_pct=ok(D("40"), "40% advance"),
        delivery_days=ok(60, "within 60 days"),
        penalty_pct_per_week=ok(D("0.1"), "0.1% per week"),
    )
    pr = pr_line()
    for rule, quote in (
        (r1_price, "104.00"),
        (r2_advance, "40% advance"),
        (r5_delivery, "within 60 days"),
        (r3_penalty, "0.1% per week"),
    ):
        result = rule(ex, pr, CFG)
        assert result.status is F
        assert result.evidence_quote == quote
