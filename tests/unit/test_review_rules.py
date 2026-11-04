from decimal import Decimal

from docgate.domain.config import DEFAULT_CONFIG
from docgate.domain.models import DayRange, FieldStatus, RuleStatus
from docgate.rules.review import (
    h1_price_slightly_over,
    h2_quantity,
    h3_payment,
    h4_delivery_window,
    h5_vat_separate,
    h6_arithmetic,
    h7_validity,
)
from tests.factories import absent, baseline_extraction, ok, pr_line

D = Decimal
P, F, U = RuleStatus.PASS, RuleStatus.FAIL, RuleStatus.UNKNOWN
CFG = DEFAULT_CONFIG


def h1(price: str) -> RuleStatus:
    return h1_price_slightly_over(baseline_extraction(price=price), pr_line(), CFG).status


def test_h1() -> None:
    assert h1("100.00") is P
    assert h1("99.00") is P
    assert h1("100.01") is F
    assert h1("102.99") is F
    assert h1("103.00") is F
    assert h1("103.01") is P  # R1 owns anything above +3%
    unit = baseline_extraction(unit=ok("dozen"))
    assert h1_price_slightly_over(unit, pr_line(), CFG).status is U
    assert h1_price_slightly_over(baseline_extraction(), None, CFG).status is U
    zero = baseline_extraction(unit_price=ok(D("0")))
    assert h1_price_slightly_over(zero, pr_line(), CFG).status is U


def h2(qty: str) -> RuleStatus:
    return h2_quantity(baseline_extraction(qty=qty), pr_line(), CFG).status


def test_h2() -> None:
    assert h2("21000") is P
    assert h2("19000") is P
    assert h2("21020") is F
    assert h2("18980") is F
    assert h2("16500") is F
    assert h2("0") is U
    assert (
        h2_quantity(
            baseline_extraction().model_copy(update={"qty": absent()}), pr_line(), CFG
        ).status
        is U
    )
    assert h2_quantity(baseline_extraction(), None, CFG).status is U


def h3(lo: int, hi: int) -> RuleStatus:
    ex = baseline_extraction(payment_days=ok(DayRange(min=lo, max=hi), f"{lo} to {hi} days"))
    return h3_payment(ex, pr_line(), CFG).status


def test_h3() -> None:
    assert h3(30, 30) is P
    assert h3(60, 60) is P
    assert h3(45, 45) is P
    assert h3(29, 29) is F
    assert h3(61, 61) is F
    assert h3(30, 90) is F
    assert h3_payment(baseline_extraction(payment_days=absent()), pr_line(), CFG).status is U


def h4(days: int) -> RuleStatus:
    ex = baseline_extraction(delivery_days=ok(days, f"within {days} days"))
    return h4_delivery_window(ex, pr_line(), CFG).status


def test_h4() -> None:
    assert h4(24) is P
    assert h4(30) is P
    assert h4(31) is F
    assert h4(45) is F
    assert h4(46) is P  # R5 owns it
    missing = baseline_extraction(delivery_days=absent())
    assert h4_delivery_window(missing, pr_line(), CFG).status is U


def test_h5() -> None:
    pr = pr_line()
    assert h5_vat_separate(baseline_extraction(), pr, CFG).status is P
    inclusive = baseline_extraction(vat_shown_separately=ok(False, "taxes included"))
    assert h5_vat_separate(inclusive, pr, CFG).status is F
    ten = baseline_extraction(vat_amount=ok(D("200000.00"), "VAT 10% 200,000.00"))
    assert h5_vat_separate(ten, pr, CFG).status is F
    for status in (FieldStatus.MISSING, FieldStatus.UNVERIFIED):
        ex = baseline_extraction(vat_shown_separately=absent(status))
        assert h5_vat_separate(ex, pr, CFG).status is U
    assert h5_vat_separate(baseline_extraction(vat_amount=absent()), pr, CFG).status is U


def test_h6() -> None:
    pr = pr_line()
    assert h6_arithmetic(baseline_extraction(), pr, CFG).status is P
    bad_sub = baseline_extraction(subtotal=ok(D("2000002.00"), "subtotal 2,000,002.00"))
    r = h6_arithmetic(bad_sub, pr, CFG)
    assert r.status is F
    assert r.evidence_quote == "subtotal 2,000,002.00"
    sub, vat = D("2000000.00"), D("300000.00")
    off2 = baseline_extraction(total=ok(sub + vat + D("0.02"), "t"))
    off1 = baseline_extraction(total=ok(sub + vat + D("0.01"), "t"))
    assert h6_arithmetic(off2, pr, CFG).status is F
    assert h6_arithmetic(off1, pr, CFG).status is P
    inclusive = baseline_extraction(
        price="94.00",
        qty="20000",
        vat_shown_separately=ok(False, "taxes included"),
        subtotal=absent(),
        vat_amount=absent(),
        total=ok(D("1880000.00"), "Total 1,880,000.00"),
    )
    assert h6_arithmetic(inclusive, pr, CFG).status is P
    assert h6_arithmetic(baseline_extraction(subtotal=absent()), pr, CFG).status is U
    # total mismatch cannot be confirmed without the VAT amount, so it stays UNKNOWN
    uncheckable = baseline_extraction(total=ok(D("1.00"), "t"), vat_amount=absent())
    assert h6_arithmetic(uncheckable, pr, CFG).status is U
    # a confirmed failure outranks an uncheckable neighbour
    wrong_line = baseline_extraction(
        subtotal=ok(D("1.00"), "s"), vat_amount=absent(), total=ok(D("5.00"), "t")
    )
    assert h6_arithmetic(wrong_line, pr, CFG).status is F


def h7(days: int) -> RuleStatus:
    ex = baseline_extraction(validity_days=ok(days, f"valid for {days} days"))
    return h7_validity(ex, pr_line(), CFG).status


def test_h7() -> None:
    assert h7(30) is P
    assert h7(29) is F
    assert h7(45) is P
    missing = baseline_extraction(validity_days=absent())
    assert h7_validity(missing, pr_line(), CFG).status is U
