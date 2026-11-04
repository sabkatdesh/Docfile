from decimal import Decimal

from docgate.compare.pr import (
    find_pr_line,
    price_comparability_problem,
    price_delta_pct,
    qty_comparability_problem,
    qty_delta_pct,
)
from docgate.domain.models import FieldStatus
from tests.factories import absent, baseline_extraction, ok, pr_line

D = Decimal


def test_find_pr_line_by_item_code() -> None:
    lines = {"B": pr_line()}
    assert find_pr_line(baseline_extraction(), lines) == lines["B"]


def test_find_pr_line_unknown_item_is_none() -> None:
    assert find_pr_line(baseline_extraction(item_code=ok("Z")), {"B": pr_line()}) is None


def test_find_pr_line_missing_code_is_none() -> None:
    ex = baseline_extraction(item_code=absent(FieldStatus.MISSING))
    assert find_pr_line(ex, {"B": pr_line()}) is None


def test_price_delta_value() -> None:
    ex = baseline_extraction(price="6.65", qty="50000")
    pr = pr_line(qty="50000", max_price="6.50")
    delta = price_delta_pct(ex, pr)
    assert delta is not None
    assert delta.quantize(D("0.01")) == D("2.31")


def test_qty_delta_value() -> None:
    ex = baseline_extraction(qty="16500")
    assert qty_delta_pct(ex, pr_line()) == D("-17.5")


def test_no_pr_line_blocks_comparison() -> None:
    assert price_comparability_problem(baseline_extraction(), None) is not None
    assert qty_comparability_problem(baseline_extraction(), None) is not None
    assert price_delta_pct(baseline_extraction(), None) is None


def test_unit_mismatch_blocks_comparison() -> None:
    ex = baseline_extraction(unit=ok("dozen"))
    reason = price_comparability_problem(ex, pr_line())
    assert reason is not None
    assert "unit" in reason
    assert qty_comparability_problem(ex, pr_line()) is not None
    assert price_delta_pct(ex, pr_line()) is None


def test_unit_comparison_ignores_case() -> None:
    ex = baseline_extraction(unit=ok("Piece"))
    assert price_comparability_problem(ex, pr_line()) is None


def test_unit_not_ok_blocks_comparison() -> None:
    ex = baseline_extraction(unit=absent())
    assert price_comparability_problem(ex, pr_line()) is not None


def test_vat_inclusive_blocks_price_not_qty() -> None:
    ex = baseline_extraction(vat_shown_separately=ok(False, "all taxes included"))
    assert price_comparability_problem(ex, pr_line()) is not None
    assert qty_comparability_problem(ex, pr_line()) is None
    assert price_delta_pct(ex, pr_line()) is None
    assert qty_delta_pct(ex, pr_line()) == D("0")


def test_qty_delta_none_when_not_comparable() -> None:
    assert qty_delta_pct(baseline_extraction(unit=ok("dozen")), pr_line()) is None
    assert qty_delta_pct(baseline_extraction(), None) is None
