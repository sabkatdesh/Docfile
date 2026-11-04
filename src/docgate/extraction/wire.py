"""What the model is asked to return. Strings exactly as printed; code parses and judges."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

# Bump when the shape changes: it is part of the recording key.
SCHEMA_VERSION = "wire-v1"


class WireField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str | None
    quote: str | None


class WireExtraction(BaseModel):
    """Every key is required (Groq strict mode); absent facts are null, never omitted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    supplier: WireField
    quotation_no: WireField
    date: WireField
    item_code: WireField
    description: WireField
    qty: WireField
    unit: WireField
    unit_price: WireField
    subtotal: WireField
    vat_amount: WireField
    total: WireField
    tax_inclusive_statement: WireField
    tin: WireField
    bin: WireField
    advance_pct: WireField
    payment_days: WireField
    delivery_days: WireField
    penalty_pct_per_week: WireField
    validity_days: WireField


WIRE_FIELDS: tuple[str, ...] = tuple(WireExtraction.model_fields)


def _drop_titles(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _drop_titles(v) for k, v in node.items() if k != "title"}
    if isinstance(node, list):
        return [_drop_titles(v) for v in node]
    return node


def strict_json_schema() -> dict[str, Any]:
    """JSON Schema for strict structured output: all keys required, no extra keys, no titles."""
    schema: dict[str, Any] = _drop_titles(WireExtraction.model_json_schema())
    return schema
