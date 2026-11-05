# ruff: noqa: RUF001  (typographic characters are the test input)
from __future__ import annotations

import pytest

from docgate.extraction.base import Outcome, absent, found
from docgate.extraction.quotes import (
    locate_quote,
    normalise,
    raw_in_quote,
    verify_candidate,
    verify_quote,
)

TEXT = (
    "1. Payment. 10% advance payable with the purchase order. Balance payable within 45 days\n"
    "after delivery and acceptance of goods.\n"
    "Unit price 6.65 – net"
)


def test_exact_match() -> None:
    assert verify_quote("10% advance payable with the purchase order", TEXT)


def test_line_wrap_and_extra_spaces_are_ignored() -> None:
    assert verify_quote("within 45 days  after delivery", TEXT)


def test_case_is_ignored() -> None:
    assert verify_quote("BALANCE PAYABLE WITHIN 45 DAYS", TEXT)


def test_dash_variants_are_equivalent() -> None:
    assert verify_quote("Unit price 6.65 - net", TEXT)
    assert verify_quote("Unit price 6.65 — net", TEXT)


def test_non_breaking_space_and_curly_quotes() -> None:
    assert normalise("a b ’x’") == "a b 'x'"


def test_quote_not_in_text_fails() -> None:
    assert not verify_quote("20% advance payable", TEXT)


@pytest.mark.parametrize("bad", [None, "", "  ", "ab", "10% ... 45 days", "10% … 45 days"])
def test_unusable_quotes_fail(bad: str | None) -> None:
    assert not verify_quote(bad, TEXT)


def test_raw_must_be_a_whole_token_in_the_quote() -> None:
    assert raw_in_quote("6.65", "Unit price 6.65 net")
    assert not raw_in_quote("0", "10% advance")  # digit inside another number
    assert not raw_in_quote("6.6", "Unit price 6.65")
    assert not raw_in_quote("65", "Unit price 6.65")
    assert raw_in_quote("1,200.00", "total 1,200.00.")
    assert raw_in_quote("10", "10% advance")


def test_verify_candidate_keeps_a_good_claim() -> None:
    cand = found("x", "10% advance payable", raw="10%")
    assert verify_candidate(cand, TEXT) == cand


def test_verify_candidate_downgrades_unverified_quote() -> None:
    out = verify_candidate(found("x", "99% advance", raw="99%"), TEXT)
    assert out.outcome is Outcome.UNREADABLE
    assert "quote" in (out.note or "")


def test_verify_candidate_downgrades_raw_not_in_quote() -> None:
    out = verify_candidate(found("x", "10% advance payable", raw="12%"), TEXT)
    assert out.outcome is Outcome.UNREADABLE


def test_verify_candidate_leaves_absent_alone() -> None:
    cand = absent()
    assert verify_candidate(cand, TEXT) is cand


# -- locate_quote: where a verified quote sits, for highlighting ---------------------------------


def test_locate_exact_quote_gives_its_span() -> None:
    quote = "10% advance payable with the purchase order"
    span = locate_quote(quote, TEXT)
    assert span is not None
    assert TEXT[span.start : span.end] == quote


def test_locate_follows_a_quote_across_a_line_wrap_and_case() -> None:
    span = locate_quote("WITHIN 45 days after delivery", TEXT)
    assert span is not None
    assert TEXT[span.start : span.end] == "within 45 days\nafter delivery"


def test_locate_follows_a_dash_variant() -> None:
    span = locate_quote("Unit price 6.65 - net", TEXT)
    assert span is not None
    assert TEXT[span.start : span.end] == "Unit price 6.65 – net"


def test_locate_returns_none_when_the_quote_is_absent_or_empty_or_stitched() -> None:
    assert locate_quote("not in the text at all", TEXT) is None
    assert locate_quote(None, TEXT) is None
    assert locate_quote("10% advance ... purchase order", TEXT) is None
    assert locate_quote("ab", TEXT) is None  # below the minimum length, like verify_quote


def test_locate_agrees_with_verify_quote_on_every_sample_pack() -> None:
    from tests.graph_support import base_texts_and_quotes

    for pack, text, quotes in base_texts_and_quotes():
        for quote in quotes:
            assert verify_quote(quote, text), (pack, quote)
            span = locate_quote(quote, text)
            assert span is not None, (pack, quote)
            assert normalise(text[span.start : span.end]) == normalise(quote)
