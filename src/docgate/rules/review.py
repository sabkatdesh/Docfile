"""Review rules H1-H7. FAIL means "Needs a person to check"."""

from __future__ import annotations

from decimal import Decimal

from docgate.compare.arithmetic import check_arithmetic
from docgate.domain.config import RuleConfig
from docgate.domain.models import Extraction, PRLine, RuleResult
from docgate.domain.money import differs_by_more_than, is_above, pct_delta
from docgate.rules.base import (
    failed,
    passed,
    price_inputs,
    qty_inputs,
    unknown,
    unknown_for_field,
)


def h1_price_slightly_over(ex: Extraction, pr: PRLine | None, cfg: RuleConfig) -> RuleResult:
    inputs = price_inputs("H1", ex, pr)
    if isinstance(inputs, RuleResult):
        return inputs
    price, line = inputs
    quote = ex.unit_price.quote
    delta = pct_delta(price, line.max_unit_price).quantize(Decimal("0.01"))
    # Above the tolerance belongs to R1; H1 covers only "above max, by no more than tolerance".
    over = price > line.max_unit_price
    if over and not is_above(price, line.max_unit_price, cfg.price_tolerance_pct):
        return failed(
            "H1", f"unit price is {delta:+}% above the PR max {line.max_unit_price}", quote
        )
    return passed("H1", "unit price is not slightly over the PR max", quote)


def h2_quantity(ex: Extraction, pr: PRLine | None, cfg: RuleConfig) -> RuleResult:
    inputs = qty_inputs("H2", ex, pr)
    if isinstance(inputs, RuleResult):
        return inputs
    qty, line = inputs
    delta = pct_delta(qty, line.qty).quantize(Decimal("0.01"))
    detail = f"quantity {qty} vs requested {line.qty} ({delta:+}%)"
    if differs_by_more_than(qty, line.qty, cfg.qty_tolerance_pct):
        return failed("H2", f"{detail} differs by more than {cfg.qty_tolerance_pct}%", ex.qty.quote)
    return passed("H2", f"{detail} is within {cfg.qty_tolerance_pct}%", ex.qty.quote)


def h3_payment(ex: Extraction, pr: PRLine | None, cfg: RuleConfig) -> RuleResult:
    f = ex.payment_days
    if not f.is_ok or f.value is None:
        return unknown_for_field("H3", "payment terms", f)
    span = f.value
    if span.min < cfg.payment_min_days or span.max > cfg.payment_max_days:
        return failed(
            "H3",
            f"payment in {span.min} to {span.max} days is outside "
            f"{cfg.payment_min_days} to {cfg.payment_max_days} days",
            f.quote,
        )
    return passed("H3", f"payment in {span.min} to {span.max} days is acceptable", f.quote)


def h4_delivery_window(ex: Extraction, pr: PRLine | None, cfg: RuleConfig) -> RuleResult:
    f = ex.delivery_days
    if not f.is_ok or f.value is None:
        return unknown_for_field("H4", "delivery time", f)
    if cfg.delivery_review_above_days < f.value <= cfg.delivery_max_days:
        return failed("H4", f"delivery in {f.value} days needs review", f.quote)
    return passed("H4", f"delivery in {f.value} days is not in the review window", f.quote)


def h5_vat_separate(ex: Extraction, pr: PRLine | None, cfg: RuleConfig) -> RuleResult:
    flag = ex.vat_shown_separately
    if not flag.is_ok:
        return unknown_for_field("H5", "VAT presentation", flag)
    if flag.value is False:
        return failed("H5", "VAT is not shown separately", flag.quote)
    vat = next(f for f in check_arithmetic(ex, cfg) if f.check == "vat")
    if vat.ok is None:
        return unknown("H5", "VAT amount cannot be checked against the subtotal", vat.quote)
    if not vat.ok:
        return failed("H5", f"VAT {vat.actual} is not {cfg.vat_rate_pct}% of subtotal", vat.quote)
    return passed("H5", f"VAT is shown separately at {cfg.vat_rate_pct}%", vat.quote)


def h6_arithmetic(ex: Extraction, pr: PRLine | None, cfg: RuleConfig) -> RuleResult:
    # The VAT-rate check belongs to H5; H6 covers line total and grand total.
    findings = [f for f in check_arithmetic(ex, cfg) if f.check != "vat"]
    for f in findings:
        if f.ok is False:
            return failed("H6", f"{f.check}: expected {f.expected} but quoted {f.actual}", f.quote)
    if any(f.ok is None for f in findings):
        return unknown("H6", "some amounts are missing, so the arithmetic cannot be checked")
    return passed("H6", "line total and total add up", ex.total.quote)


def h7_validity(ex: Extraction, pr: PRLine | None, cfg: RuleConfig) -> RuleResult:
    f = ex.validity_days
    if not f.is_ok or f.value is None:
        return unknown_for_field("H7", "quotation validity", f)
    if f.value < cfg.validity_min_days:
        return failed("H7", f"valid for {f.value} days, under {cfg.validity_min_days}", f.quote)
    return passed("H7", f"valid for {f.value} days", f.quote)
