"""Turn a value exactly as printed into a typed value. Strict: anything ambiguous raises."""

from __future__ import annotations

import datetime
import re
from collections.abc import Callable
from decimal import Decimal

from docgate.domain.config import RuleConfig
from docgate.domain.models import DayRange


class ParseError(ValueError):
    """The printed value cannot be read unambiguously."""


# Western grouping only. Lakh grouping (12,34,567) is rejected on purpose: it escalates.
_AMOUNT = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
_NO_ADVANCE = re.compile(r"no advance(?: payment)?(?: required)?\.?", re.IGNORECASE)
_DURATION = re.compile(r"(\d+)\s*(day|week)s?", re.IGNORECASE)
_RANGE = re.compile(r"(\d+)(?:\s*(?:to|-)\s*(\d+))?\s*(day|week)s?", re.IGNORECASE)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_amount(raw: str) -> Decimal:
    s = raw.strip()
    if not _AMOUNT.fullmatch(s):
        raise ParseError(f"not an unambiguous amount: {raw!r}")
    return Decimal(s.replace(",", ""))


def parse_percent(raw: str) -> Decimal:
    s = raw.strip()
    return parse_amount(s[:-1] if s.endswith("%") else s)


def parse_advance(raw: str, _cfg: RuleConfig | None = None) -> Decimal:
    if _NO_ADVANCE.fullmatch(raw.strip()):
        return Decimal(0)
    return parse_percent(raw)


def _days(amount: str, unit: str, cfg: RuleConfig) -> int:
    n = int(amount)
    return n * cfg.days_per_week if unit.lower() == "week" else n


def parse_days(raw: str, cfg: RuleConfig) -> int:
    m = _DURATION.fullmatch(raw.strip())
    if not m:
        raise ParseError(f"not a duration in days or weeks: {raw!r}")
    return _days(m.group(1), m.group(2), cfg)


def parse_day_range(raw: str, cfg: RuleConfig) -> DayRange:
    m = _RANGE.fullmatch(raw.strip())
    if not m:
        raise ParseError(f"not a duration or range: {raw!r}")
    low = _days(m.group(1), m.group(3), cfg)
    high = _days(m.group(2) or m.group(1), m.group(3), cfg)
    try:
        return DayRange(min=low, max=high)
    except ValueError as exc:
        raise ParseError(f"inverted range: {raw!r}") from exc


def parse_date(raw: str) -> datetime.date:
    s = raw.strip()
    if not _DATE.fullmatch(s):
        raise ParseError(f"not an ISO date: {raw!r}")
    try:
        return datetime.date.fromisoformat(s)
    except ValueError as exc:
        raise ParseError(f"invalid date: {raw!r}") from exc


def parse_text(raw: str, _cfg: RuleConfig | None = None) -> str:
    s = " ".join(raw.split())
    if not s:
        raise ParseError("empty text")
    return s


Parser = Callable[[str, RuleConfig], object]

FIELD_PARSERS: dict[str, Parser] = {
    "supplier": parse_text,
    "quotation_no": parse_text,
    "date": lambda raw, _cfg: parse_date(raw),
    "item_code": parse_text,
    "description": parse_text,
    "qty": lambda raw, _cfg: parse_amount(raw),
    "unit": parse_text,
    "unit_price": lambda raw, _cfg: parse_amount(raw),
    "subtotal": lambda raw, _cfg: parse_amount(raw),
    "vat_amount": lambda raw, _cfg: parse_amount(raw),
    "total": lambda raw, _cfg: parse_amount(raw),
    "tin": parse_text,
    "bin": parse_text,
    "advance_pct": parse_advance,
    "payment_days": parse_day_range,
    "delivery_days": parse_days,
    "penalty_pct_per_week": lambda raw, _cfg: parse_percent(raw),
    "validity_days": parse_days,
}
