"""Builders so each boundary test changes exactly one thing from a fully passing pack."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from docgate.domain.models import DayRange, Extraction, Field, FieldStatus, PRLine


def ok[T](value: T, quote: str = "q") -> Field[T]:
    return Field[T](value=value, quote=quote, status=FieldStatus.OK)


def absent[T](status: FieldStatus = FieldStatus.MISSING) -> Field[T]:
    return Field[T](status=status)


def pr_line(
    item: str = "B", qty: str = "20000", max_price: str = "100.00", unit: str = "piece"
) -> PRLine:
    return PRLine(
        pr_number="PR-TEST",
        item_code=item,
        description="test item",
        unit=unit,
        qty=Decimal(qty),
        max_unit_price=Decimal(max_price),
    )


def baseline_extraction(
    price: str = "100.00", qty: str = "20000", **overrides: Field[Any]
) -> Extraction:
    """A pack that passes every rule against `pr_line()`; totals follow `price` and `qty`."""
    p, q = Decimal(price), Decimal(qty)
    subtotal = p * q
    vat = subtotal * Decimal("0.15")
    fields: dict[str, Field[Any]] = {
        "supplier": ok("Test Supplier"),
        "quotation_no": ok("QT-1"),
        "item_code": ok("B"),
        "description": ok("test item"),
        "qty": ok(q, f"qty {q}"),
        "unit": ok("piece"),
        "unit_price": ok(p, f"price {p}"),
        "subtotal": ok(subtotal, f"subtotal {subtotal}"),
        "vat_amount": ok(vat, f"VAT 15% {vat}"),
        "total": ok(subtotal + vat, f"total {subtotal + vat}"),
        "vat_shown_separately": ok(True, "VAT 15%"),
        "tin": ok("101458013391", "TIN: 101458013391"),
        "bin": ok("000170141-0101", "BIN: 000170141-0101"),
        "advance_pct": ok(Decimal("10"), "10% advance"),
        "payment_days": ok(DayRange(min=45, max=45), "within 45 days"),
        "delivery_days": ok(24, "within 24 days"),
        "penalty_pct_per_week": ok(Decimal("1"), "1% per week"),
        "validity_days": ok(45, "valid for 45 days"),
    }
    fields.update(overrides)
    return Extraction(**fields)
