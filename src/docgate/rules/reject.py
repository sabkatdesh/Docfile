"""Reject rules R1-R5. FAIL means the pack must be rejected."""

from __future__ import annotations

from decimal import Decimal

from docgate.domain.config import RuleConfig
from docgate.domain.models import Extraction, FieldStatus, PRLine, RuleResult
from docgate.domain.money import is_above, pct_delta
from docgate.rules.base import failed, passed, price_inputs, unknown, unknown_for_field


def r1_price(ex: Extraction, pr: PRLine | None, cfg: RuleConfig) -> RuleResult:
    inputs = price_inputs("R1", ex, pr)
    if isinstance(inputs, RuleResult):
        return inputs
    price, line = inputs
    quote = ex.unit_price.quote
    delta = pct_delta(price, line.max_unit_price).quantize(Decimal("0.01"))
    detail = f"unit price {price} vs PR max {line.max_unit_price} ({delta:+}%)"
    if is_above(price, line.max_unit_price, cfg.price_tolerance_pct):
        return failed("R1", f"{detail} is more than {cfg.price_tolerance_pct}% above max", quote)
    return passed("R1", f"{detail} is within the {cfg.price_tolerance_pct}% limit", quote)


def r2_advance(ex: Extraction, pr: PRLine | None, cfg: RuleConfig) -> RuleResult:
    value = ex.advance_pct.value
    if not ex.advance_pct.is_ok or value is None:
        return unknown_for_field("R2", "advance payment", ex.advance_pct)
    quote = ex.advance_pct.quote
    if not 0 <= value <= 100:
        return unknown("R2", f"advance of {value}% is not a valid percentage", quote)
    if value > cfg.advance_max_pct:
        return failed("R2", f"advance {value}% is more than {cfg.advance_max_pct}%", quote)
    return passed("R2", f"advance {value}% is within {cfg.advance_max_pct}%", quote)


def r3_penalty(ex: Extraction, pr: PRLine | None, cfg: RuleConfig) -> RuleResult:
    f = ex.penalty_pct_per_week
    # Absent from the document is the Reject condition; unreadable or conflicting is not.
    if f.status is FieldStatus.MISSING:
        return failed("R3", "no late-delivery penalty clause found")
    if not f.is_ok or f.value is None:
        return unknown_for_field("R3", "late-delivery penalty", f)
    if f.value < 0:
        return unknown("R3", f"penalty rate {f.value}% is not plausible", f.quote)
    if f.value < cfg.penalty_min_pct_per_week:
        return failed(
            "R3", f"penalty {f.value}% per week is below {cfg.penalty_min_pct_per_week}%", f.quote
        )
    return passed(
        "R3", f"penalty {f.value}% per week meets {cfg.penalty_min_pct_per_week}%", f.quote
    )


def r4_tax_ids(ex: Extraction, pr: PRLine | None, cfg: RuleConfig) -> RuleResult:
    ids = (("TIN", ex.tin), ("BIN", ex.bin))
    missing = [name for name, f in ids if f.status is FieldStatus.MISSING]
    if missing:
        return failed("R4", f"{' and '.join(missing)} missing from the quotation")
    for name, f in ids:
        if not f.is_ok:
            return unknown_for_field("R4", name, f)
    return passed("R4", "TIN and BIN are present", ex.tin.quote)


def r5_delivery(ex: Extraction, pr: PRLine | None, cfg: RuleConfig) -> RuleResult:
    f = ex.delivery_days
    if not f.is_ok or f.value is None:
        return unknown_for_field("R5", "delivery time", f)
    if f.value <= 0:
        return unknown("R5", f"delivery of {f.value} days is not plausible", f.quote)
    if f.value > cfg.delivery_max_days:
        return failed(
            "R5", f"delivery in {f.value} days is later than {cfg.delivery_max_days}", f.quote
        )
    return passed("R5", f"delivery in {f.value} days is within {cfg.delivery_max_days}", f.quote)
