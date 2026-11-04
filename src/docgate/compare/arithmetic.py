"""Recompute the quotation's own numbers and compare them to what it states."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from docgate.domain.config import RuleConfig
from docgate.domain.models import Extraction

CheckName = Literal["line_total", "vat", "total"]


@dataclass(frozen=True)
class ArithmeticFinding:
    check: CheckName
    expected: Decimal | None
    actual: Decimal | None
    ok: bool | None  # None: inputs unusable, cannot check
    quote: str | None


def _finding(
    check: CheckName,
    expected: Decimal | None,
    actual: Decimal | None,
    quote: str | None,
    config: RuleConfig,
) -> ArithmeticFinding:
    if expected is None or actual is None:
        return ArithmeticFinding(check, expected, actual, None, quote)
    ok = abs(expected - actual) <= config.arithmetic_tolerance
    return ArithmeticFinding(check, expected, actual, ok, quote)


def check_arithmetic(ex: Extraction, config: RuleConfig) -> list[ArithmeticFinding]:
    price, qty = ex.unit_price.value, ex.qty.value
    line = price * qty if price is not None and qty is not None else None
    subtotal, vat, total = ex.subtotal.value, ex.vat_amount.value, ex.total.value

    if not ex.vat_shown_separately.is_ok:
        return [
            # Which total the line should match depends on the VAT flag, so nothing is checkable.
            _finding("line_total", None, subtotal, ex.subtotal.quote, config),
            _finding("vat", None, vat, ex.vat_amount.quote, config),
            _finding("total", None, total, ex.total.quote, config),
        ]
    if ex.vat_shown_separately.value is False:
        # Tax-inclusive quote: the only statable relation is quantity x price = total.
        return [_finding("line_total", line, total, ex.total.quote, config)]

    expected_vat = subtotal * config.vat_rate_pct / 100 if subtotal is not None else None
    expected_total = subtotal + vat if subtotal is not None and vat is not None else None
    return [
        _finding("line_total", line, subtotal, ex.subtotal.quote, config),
        _finding("vat", expected_vat, vat, ex.vat_amount.quote, config),
        _finding("total", expected_total, total, ex.total.quote, config),
    ]
