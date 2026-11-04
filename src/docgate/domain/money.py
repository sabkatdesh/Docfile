"""Decimal helpers. Money is never a float, so a float anywhere is a bug we want loud."""

from __future__ import annotations

import re
from decimal import Decimal

_AMOUNT = re.compile(r"-?\d+(?:\.\d+)?")


def to_money(value: str | int | Decimal) -> Decimal:
    # bool is an int subclass; True would silently become 1.
    if isinstance(value, bool) or not isinstance(value, str | int | Decimal):
        raise TypeError(f"money must be str, int or Decimal, got {type(value).__name__}")
    return Decimal(value)


def parse_money(text: str) -> Decimal:
    """Parse '1,234.50', 'BDT 322,000' or 'Tk. 6.40'. Anything ambiguous raises."""
    cleaned = text.replace(",", "")
    matches = _AMOUNT.findall(cleaned)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one amount in {text!r}")
    return Decimal(matches[0])


def pct_delta(actual: Decimal, base: Decimal) -> Decimal:
    """Percent difference of `actual` from `base`; positive means above base."""
    if base == 0:
        raise ZeroDivisionError("cannot compute a percentage of a zero base")
    return (actual - base) / base * 100


def is_above(actual: Decimal, base: Decimal, pct: Decimal) -> bool:
    """True iff `actual` exceeds `base` by strictly more than `pct` percent.

    Cross-multiplied so a boundary like exactly +3% is decided exactly, never by a rounded quotient.
    """
    return actual * 100 > base * (100 + pct)


def differs_by_more_than(actual: Decimal, base: Decimal, pct: Decimal) -> bool:
    """True iff `actual` is more than `pct` percent away from `base`, in either direction."""
    return abs(actual - base) * 100 > base * pct
