"""The mutation harness is itself checked, so a harness bug cannot decide a verdict."""

from __future__ import annotations

from decimal import Decimal

import pytest

from docgate.domain.models import Decision
from docgate.extraction.quotes import verify_quote
from tests.mutation.harness import (
    Edit,
    HarnessError,
    Mutation,
    apply_edits,
    base_response,
    base_text,
    mutated_inputs,
    non_pass,
    reprice,
    run_mutant,
    unverifiable_fields,
)

IDENTITY = Mutation("identity", Decision.APPROVE, {})


def test_an_edit_must_occur_exactly_the_expected_number_of_times() -> None:
    with pytest.raises(HarnessError, match="occurs 0 times"):
        apply_edits("abc", (Edit("zzz", "y"),))
    with pytest.raises(HarnessError, match="occurs 2 times"):
        apply_edits("aa", (Edit("a", "b"),))
    assert apply_edits("aa", (Edit("a", "b", count=2),)) == "bb"


def test_an_unchanged_pack_still_approves_through_the_scripted_provider() -> None:
    state = run_mutant(IDENTITY)
    assert state["verdict"].decision is Decision.APPROVE
    assert non_pass(state) == {}
    assert state["errors"] == []


def test_consistent_mutation_keeps_every_quote_verifiable() -> None:
    m = Mutation(
        "advance",
        Decision.REJECT,
        {},
        edits=(Edit("10% advance", "21% advance"),),
        values={"advance_pct": "21%"},
    )
    text, response = mutated_inputs(m)
    assert "21% advance" in text and "10% advance" not in text
    assert response["advance_pct"]["value"] == "21%"
    assert "21% advance" in response["advance_pct"]["quote"]
    assert all(verify_quote(w["quote"], text) for w in response.values() if w["quote"])


def test_stale_mutation_changes_only_the_text() -> None:
    m = Mutation("advance", Decision.REJECT, {}, edits=(Edit("10% advance", "21% advance"),))
    text, response = mutated_inputs(m, stale=True)
    assert "21% advance" in text
    assert response == base_response(1)  # the recorded extraction is untouched
    assert unverifiable_fields(m) == ["advance_pct"]


def test_a_harness_bug_is_reported_as_one_not_as_a_verdict() -> None:
    # The edit spans a line wrap, so the (single-line) recorded quote cannot be rewritten with it.
    wrap = Edit("delivery and\nacceptance", "delivery and\nfinal acceptance")
    bad = Mutation("bad", Decision.REJECT, {}, edits=(wrap,))
    with pytest.raises(HarnessError, match="quotes no longer in the text"):
        mutated_inputs(bad)
    with pytest.raises(HarnessError, match="occurs 0 times"):
        mutated_inputs(Mutation("x", Decision.REJECT, {}, edits=(Edit("no such text", "y"),)))


def test_whitespace_transform_is_applied_to_the_text() -> None:
    m = Mutation("ws", Decision.APPROVE, {}, transform=lambda t: t.replace("\n", "\n\n"))
    text, _ = mutated_inputs(m)
    assert "\n\n" in text and "\n\n" not in base_text(1)


def _pieces(qty: int, price: str) -> dict[str, str | None]:
    return reprice(qty, price)[1]


def test_reprice_recomputes_every_dependent_figure_exactly() -> None:
    up = _pieces(12_000, "494.88")  # 480.00 x 1.031
    assert (up["subtotal"], up["vat_amount"], up["total"]) == (
        "5,938,560.00",
        "890,784.00",
        "6,829,344.00",
    )
    fewer = _pieces(11_280, "472.00")  # 12,000 less 6%
    assert (fewer["subtotal"], fewer["vat_amount"], fewer["total"]) == (
        "5,324,160.00",
        "798,624.00",
        "6,122,784.00",
    )
    assert Decimal("494.88") == Decimal("480.00") * Decimal("1.031")


def test_reprice_to_the_original_numbers_changes_nothing() -> None:
    edits, values = reprice(12_000, "472.00")
    state = run_mutant(Mutation("same", Decision.APPROVE, {}, edits=edits, values=values))
    assert state["verdict"].decision is Decision.APPROVE
    assert non_pass(state) == {}
