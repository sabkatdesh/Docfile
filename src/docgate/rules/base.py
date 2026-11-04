"""Shared building blocks for rules: result builders and guarded input access."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from docgate.compare.pr import price_comparability_problem, qty_comparability_problem
from docgate.domain.config import RuleConfig
from docgate.domain.models import Extraction, Field, PRLine, RuleResult, RuleStatus

Rule = Callable[[Extraction, PRLine | None, RuleConfig], RuleResult]


def passed(rule_id: str, message: str, quote: str | None = None) -> RuleResult:
    return RuleResult(
        rule_id=rule_id, status=RuleStatus.PASS, message=message, evidence_quote=quote
    )


def failed(rule_id: str, message: str, quote: str | None = None) -> RuleResult:
    return RuleResult(
        rule_id=rule_id, status=RuleStatus.FAIL, message=message, evidence_quote=quote
    )


def unknown(rule_id: str, message: str, quote: str | None = None) -> RuleResult:
    return RuleResult(
        rule_id=rule_id, status=RuleStatus.UNKNOWN, message=message, evidence_quote=quote
    )


def unknown_for_field(rule_id: str, name: str, field: Field[Any]) -> RuleResult:
    if field.is_ok:
        raise ValueError("unknown_for_field called with a usable field")
    return unknown(rule_id, f"{name} is {field.status.value}; a person must check")


def positive_decimal(rule_id: str, name: str, field: Field[Decimal]) -> Decimal | RuleResult:
    """The value, or an UNKNOWN result when it is absent, unverified or implausible."""
    if not field.is_ok or field.value is None:
        return unknown_for_field(rule_id, name, field)
    if field.value <= 0:
        return unknown(rule_id, f"{name} is {field.value}, which is not plausible", field.quote)
    return field.value


def price_inputs(
    rule_id: str, ex: Extraction, pr: PRLine | None
) -> tuple[Decimal, PRLine] | RuleResult:
    problem = price_comparability_problem(ex, pr)
    if problem or pr is None:
        return unknown(rule_id, f"unit price cannot be compared: {problem}")
    price = positive_decimal(rule_id, "unit price", ex.unit_price)
    if isinstance(price, RuleResult):
        return price
    return price, pr


def qty_inputs(
    rule_id: str, ex: Extraction, pr: PRLine | None
) -> tuple[Decimal, PRLine] | RuleResult:
    problem = qty_comparability_problem(ex, pr)
    if problem or pr is None:
        return unknown(rule_id, f"quantity cannot be compared: {problem}")
    qty = positive_decimal(rule_id, "quantity", ex.qty)
    if isinstance(qty, RuleResult):
        return qty
    return qty, pr
