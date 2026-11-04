from __future__ import annotations

from decimal import Decimal

import pytest

from docgate.domain.config import DEFAULT_CONFIG as CFG
from docgate.domain.models import DayRange
from docgate.extraction.parsing import (
    ParseError,
    parse_advance,
    parse_amount,
    parse_date,
    parse_day_range,
    parse_days,
    parse_percent,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("6.65", "6.65"),
        ("1,200.00", "1200.00"),
        ("472.00", "472.00"),
        ("5,664,000.00", "5664000.00"),
        ("12000", "12000"),
        (" 800 ", "800"),
    ],
)
def test_amount(raw: str, expected: str) -> None:
    value = parse_amount(raw)
    assert value == Decimal(expected)
    assert str(value) == expected  # trailing zeros survive, never via float


@pytest.mark.parametrize("raw", ["1.200,00", "1,20", "abc", "", "12,34,567.00", "6.65 BDT", "-5"])
def test_amount_rejects_ambiguous(raw: str) -> None:
    with pytest.raises(ParseError):
        parse_amount(raw)


def test_percent() -> None:
    assert parse_percent("10%") == Decimal("10")
    assert parse_percent("0.75%") == Decimal("0.75")
    assert parse_percent("1") == Decimal("1")
    with pytest.raises(ParseError):
        parse_percent("ten percent")


def test_advance_none_is_zero() -> None:
    assert parse_advance("No advance payment required") == Decimal("0")
    assert parse_advance("40%") == Decimal("40")


@pytest.mark.parametrize(
    ("raw", "days"),
    [("24 days", 24), ("4 weeks", 28), ("1 week", 7), ("45 DAYS", 45)],
)
def test_days(raw: str, days: int) -> None:
    assert parse_days(raw, CFG) == days


@pytest.mark.parametrize("raw", ["soon", "2.5 weeks", "within 24 days", "", "24"])
def test_days_rejects(raw: str) -> None:
    with pytest.raises(ParseError):
        parse_days(raw, CFG)


def test_day_range() -> None:
    assert parse_day_range("30 to 90 days", CFG) == DayRange(min=30, max=90)
    assert parse_day_range("45 days", CFG) == DayRange(min=45, max=45)
    assert parse_day_range("2 weeks", CFG) == DayRange(min=14, max=14)
    with pytest.raises(ParseError):
        parse_day_range("90 to 30 days", CFG)


def test_date() -> None:
    assert parse_date("2026-10-21").isoformat() == "2026-10-21"
    for bad in ("21/10/2026", "2026-13-01"):
        with pytest.raises(ParseError):
            parse_date(bad)
