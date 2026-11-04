"""Match a quoted item to its PR line and say whether the two can be compared at all."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from docgate.domain.models import Extraction, PRLine
from docgate.domain.money import pct_delta


def find_pr_line(ex: Extraction, lines: Mapping[str, PRLine]) -> PRLine | None:
    if not ex.item_code.is_ok or ex.item_code.value is None:
        return None
    return lines.get(ex.item_code.value)


def qty_comparability_problem(ex: Extraction, pr: PRLine | None) -> str | None:
    """Why the quantity cannot be compared to the PR, or None if it can."""
    if pr is None:
        return "no matching purchase request line"
    if not ex.unit.is_ok or ex.unit.value is None:
        return f"quoted unit is {ex.unit.status}"
    # A price or quantity per another unit (dozen vs piece) would compare wrongly, never guess.
    if ex.unit.value.strip().lower() != pr.unit.strip().lower():
        return f"quoted unit {ex.unit.value!r} differs from requested unit {pr.unit!r}"
    return None


def price_comparability_problem(ex: Extraction, pr: PRLine | None) -> str | None:
    problem = qty_comparability_problem(ex, pr)
    if problem:
        return problem
    # The PR maximum is not stated to include VAT, so a tax-inclusive price cannot be judged.
    if ex.vat_shown_separately.is_ok and ex.vat_shown_separately.value is False:
        return "quoted price includes VAT and cannot be compared to the PR maximum"
    return None


def price_delta_pct(ex: Extraction, pr: PRLine | None) -> Decimal | None:
    """Display value only; rules decide with exact cross-multiplied comparisons."""
    if pr is None or price_comparability_problem(ex, pr) or ex.unit_price.value is None:
        return None
    return pct_delta(ex.unit_price.value, pr.max_unit_price)


def qty_delta_pct(ex: Extraction, pr: PRLine | None) -> Decimal | None:
    if pr is None or qty_comparability_problem(ex, pr) or ex.qty.value is None:
        return None
    return pct_delta(ex.qty.value, pr.qty)
