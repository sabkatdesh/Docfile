from __future__ import annotations

from decimal import Decimal

from docgate.compare.summary import compare
from docgate.domain.config import DEFAULT_CONFIG
from docgate.domain.models import FieldStatus
from tests.factories import absent, baseline_extraction, ok, pr_line

LINES = {"B": pr_line()}


def test_deltas_and_arithmetic_for_a_clean_pack() -> None:
    c = compare(baseline_extraction(price="102.00"), LINES, DEFAULT_CONFIG)
    assert c.pr_line == LINES["B"]
    assert c.price_delta_pct == Decimal("2")
    assert c.qty_delta_pct == Decimal("0")
    assert c.price_note is None
    assert all(a.ok for a in c.arithmetic)


def test_unknown_item_has_no_pr_line_and_no_deltas() -> None:
    c = compare(baseline_extraction(item_code=ok("Z")), LINES, DEFAULT_CONFIG)
    assert c.pr_line is None
    assert c.price_delta_pct is None and c.qty_delta_pct is None
    assert c.price_note is not None


def test_vat_inclusive_price_gives_a_note_not_a_delta() -> None:
    ex = baseline_extraction(vat_shown_separately=ok(False, "all taxes included"))
    c = compare(ex, LINES, DEFAULT_CONFIG)
    assert c.price_delta_pct is None
    assert c.price_note is not None and "VAT" in c.price_note
    assert c.qty_delta_pct == Decimal("0")  # quantity is still comparable


def test_missing_item_code() -> None:
    ex = baseline_extraction(item_code=absent(FieldStatus.UNVERIFIED))
    assert compare(ex, LINES, DEFAULT_CONFIG).pr_line is None
