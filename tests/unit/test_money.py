from decimal import Decimal

import pytest

from docgate.domain.money import parse_money, pct_delta, to_money


def test_to_money_accepts_str_int_decimal() -> None:
    assert to_money("6.50") == Decimal("6.50")
    assert to_money(20000) == Decimal(20000)
    assert to_money(Decimal("1.1")) == Decimal("1.1")


def test_to_money_rejects_float() -> None:
    with pytest.raises(TypeError):
        to_money(6.5)  # type: ignore[arg-type]


def test_to_money_rejects_bool() -> None:
    with pytest.raises(TypeError):
        to_money(True)


def test_parse_money_strips_separators_and_currency() -> None:
    assert parse_money("1,234.50") == Decimal("1234.50")
    assert parse_money("BDT 322,000") == Decimal("322000")
    assert parse_money("Tk. 6.40") == Decimal("6.40")


@pytest.mark.parametrize("text", ["", "abc", "1.2.3", "12 13"])
def test_parse_money_rejects_garbage(text: str) -> None:
    with pytest.raises(ValueError):
        parse_money(text)


def test_pct_delta_is_exact() -> None:
    assert pct_delta(Decimal("229"), Decimal("210")) == pytest.approx(
        Decimal("9.047619"), abs=Decimal("0.0001")
    )
    assert pct_delta(Decimal("216.3"), Decimal("210")) == Decimal("3")
    assert pct_delta(Decimal("16500"), Decimal("20000")) == Decimal("-17.5")


def test_pct_delta_zero_base_raises() -> None:
    with pytest.raises(ZeroDivisionError):
        pct_delta(Decimal("1"), Decimal("0"))
