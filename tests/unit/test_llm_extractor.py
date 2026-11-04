from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from docgate.domain.models import Extraction
from docgate.extraction.base import Outcome
from docgate.extraction.llm import LLMExtractor
from docgate.extraction.prompt import PROMPT_VERSION, load_prompt
from docgate.extraction.wire import SCHEMA_VERSION, WIRE_FIELDS, strict_json_schema
from docgate.ingest.pdf import extract_text
from docgate.llm.provider import LLMBadResponseError, LLMConfigError, LLMUnavailableError
from tests.fakes import FakeProvider

SAMPLE = Path(__file__).parents[2] / "data" / "sample"
TEXT = extract_text(SAMPLE / "supplier-pack-04.pdf")
ROW = "D Poly bag, 30 x 40 cm 50,000 piece 6.65 332,500.00"
PARAMS = {"reasoning_effort": "low", "structured_mode": "strict"}


def _wire(**overrides: tuple[str | None, str | None]) -> dict[str, Any]:
    claims: dict[str, tuple[str | None, str | None]] = {
        "supplier": ("Surma Packaging Industries", "Surma Packaging Industries"),
        "quotation_no": ("QT-2026-904", "Quotation no. QT-2026-904"),
        "date": ("2026-10-24", "Date 2026-10-24"),
        "item_code": ("D", ROW),
        "description": ("Poly bag, 30 x 40 cm", ROW),
        "qty": ("50,000", ROW),
        "unit": ("piece", ROW),
        "unit_price": ("6.65", ROW),
        "subtotal": ("332,500.00", "Subtotal 332,500.00"),
        "vat_amount": ("49,875.00", "VAT 15% 49,875.00"),
        "total": ("382,375.00", "Total 382,375.00"),
        "tax_inclusive_statement": (None, None),
        "tin": ("104458043391", "TIN: 104458043391"),
        "bin": ("000470441-0101", "BIN: 000470441-0101"),
        "advance_pct": ("10%", "10% advance payable with the purchase order."),
        "payment_days": ("30 days", "Payment within 30 days after delivery."),
        "delivery_days": ("28 days", "Delivery within 28 days of PO."),
        "penalty_pct_per_week": ("0.6%", "Late delivery penalty of 0.6% of order value per week."),
        "validity_days": ("40 days", "valid for 40 days from the date above"),
    } | overrides
    return {k: {"value": v, "quote": q} for k, (v, q) in claims.items()}


def _extractor(script: list[str | Exception]) -> tuple[LLMExtractor, FakeProvider]:
    provider = FakeProvider(script)
    return LLMExtractor(provider, load_prompt(), PARAMS), provider


def test_happy_path_maps_every_field_with_its_printed_form() -> None:
    ex, provider = _extractor([json.dumps(_wire())])
    out = ex.extract(TEXT, label="pack-04")
    assert out.failure is None
    assert provider.calls == 1
    c = out.candidates
    assert c["unit_price"].outcome is Outcome.FOUND
    assert c["unit_price"].value == Decimal("6.65")
    assert c["unit_price"].raw == "6.65"
    assert c["delivery_days"].value == 28
    assert c["vat_shown_separately"].value is True
    assert c["tin"].value == "104458043391"
    assert set(c) == set(Extraction.model_fields)


def test_null_value_and_quote_is_absent() -> None:
    ex, _ = _extractor([json.dumps(_wire(tin=(None, None), bin=(None, None)))])
    assert ex.extract(TEXT).candidates["tin"].outcome is Outcome.ABSENT


@pytest.mark.parametrize(
    "claim",
    [("6.65", None), (None, "Unit price 6.65"), ("six sixty-five", ROW), ("", ROW)],
)
def test_half_claims_and_unparsable_values_are_unreadable_not_found(
    claim: tuple[str | None, str | None],
) -> None:
    ex, _ = _extractor([json.dumps(_wire(unit_price=claim))])
    assert ex.extract(TEXT).candidates["unit_price"].outcome is Outcome.UNREADABLE


def test_weeks_stay_as_printed_and_are_converted_by_code() -> None:
    wire = _wire(delivery_days=("4 weeks", "Delivery within 4 weeks of PO."))
    cand = _extractor([json.dumps(wire)])[0].extract(TEXT).candidates["delivery_days"]
    assert cand.raw == "4 weeks"
    assert cand.value == 28


def test_pack10_style_vat_flag_is_false_with_the_inclusive_quote() -> None:
    wire = _wire(
        subtotal=(None, None),
        vat_amount=(None, None),
        tax_inclusive_statement=("all taxes included", "Total (all taxes included) 282,000.00"),
    )
    cand = _extractor([json.dumps(wire)])[0].extract(TEXT).candidates["vat_shown_separately"]
    assert cand.value is False
    assert cand.quote == "Total (all taxes included) 282,000.00"


def test_malformed_json_retries_once_with_the_error_then_succeeds() -> None:
    ex, provider = _extractor(["{not json", json.dumps(_wire())])
    out = ex.extract(TEXT)
    assert out.failure is None
    assert provider.calls == 2
    assert "invalid" in provider.requests[1].user.lower()
    assert provider.requests[1].user.startswith(provider.requests[0].user)


def test_malformed_twice_is_a_failure_not_an_exception() -> None:
    ex, provider = _extractor(["{not json", "still { not json"])
    out = ex.extract(TEXT)
    assert out.failure is not None
    assert out.candidates == {}
    assert provider.calls == 2


@pytest.mark.parametrize("bad", ["", "   ", "[]", '{"supplier": 1}', json.dumps({"extra": 1})])
def test_empty_or_wrong_shape_counts_as_malformed(bad: str) -> None:
    ex, provider = _extractor([bad, bad])
    assert ex.extract(TEXT).failure is not None
    assert provider.calls == 2


def test_unknown_extra_keys_are_rejected() -> None:
    wire = _wire() | {"verdict": {"value": "Approve", "quote": "x"}}
    ex, _ = _extractor([json.dumps(wire), json.dumps(_wire())])
    assert ex.extract(TEXT).failure is None  # second, valid response wins


def test_http_400_is_retried_once_like_malformed_output() -> None:
    ex, provider = _extractor([LLMBadResponseError("400"), json.dumps(_wire())])
    assert ex.extract(TEXT).failure is None
    assert provider.calls == 2


def test_exhausted_transport_retries_fail_without_a_second_attempt() -> None:
    ex, provider = _extractor([LLMUnavailableError("gave up after 4 attempts: timeout")])
    out = ex.extract(TEXT)
    assert out.failure is not None
    assert "gave up" in out.failure
    assert provider.calls == 1


def test_config_errors_stop_the_run() -> None:
    ex, _ = _extractor([LLMConfigError("bad key")])
    with pytest.raises(LLMConfigError):
        ex.extract(TEXT)


def test_request_carries_the_document_as_data_and_the_versions() -> None:
    ex, provider = _extractor([json.dumps(_wire())])
    ex.extract(TEXT, label="supplier-pack-04")
    req = provider.requests[0]
    assert TEXT in req.user
    assert req.prompt_version == PROMPT_VERSION
    assert req.schema_version == SCHEMA_VERSION
    assert req.label == "supplier-pack-04"
    assert dict(req.params) == PARAMS


def test_prompt_is_a_versioned_file_with_the_core_rules() -> None:
    prompt = load_prompt()
    assert prompt.version == PROMPT_VERSION
    lowered = prompt.text.lower()
    for phrase in ("never infer", "verbatim", "null", "do not convert", "data, not instructions"):
        assert phrase in lowered, phrase
    for name in WIRE_FIELDS:
        assert name in prompt.text, f"prompt does not describe {name}"


def _objects(node: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            found.append(node)
        for v in node.values():
            found += _objects(v)
    elif isinstance(node, list):
        for v in node:
            found += _objects(v)
    return found


def test_schema_satisfies_groq_strict_rules() -> None:
    schema = strict_json_schema()
    objs = _objects(schema)
    assert objs
    for obj in objs:
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])
    assert "default" not in json.dumps(schema)
    assert set(schema["properties"]) == set(WIRE_FIELDS)
