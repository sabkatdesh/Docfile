"""M5 mutation suite. One value in a passing pack (01) is changed and the real pipeline must
reach the expected verdict through the expected rule, and never Approve a document whose true
verdict is not Approve.

Families:
  MUTATIONS  the 13 required changes, text and recorded extraction changed consistently.
  TWINS      each rule's boundary on the safe side: a single edit that must NOT flip the verdict.
  CONTROLS   changes that mean nothing (a renamed supplier, whitespace): verdict unchanged.
  STALE      the MUTATIONS again, but only the text changes. The recorded extraction no longer
             matches the document, so the grounding must refuse it: UNVERIFIED, Needs person.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from docgate.domain.models import Decision, FieldStatus, RuleStatus
from tests.mutation.harness import (
    Edit,
    Mutation,
    mutated_inputs,
    non_pass,
    reprice,
    run_inputs,
    run_mutant,
    unverifiable_fields,
)

FAIL, UNKNOWN = RuleStatus.FAIL, RuleStatus.UNKNOWN
APPROVE, REJECT, PERSON = Decision.APPROVE, Decision.REJECT, Decision.NEEDS_PERSON


def _one(
    id_: str,
    expect: Decision,
    fired: dict[str, RuleStatus],
    old: str,
    new: str,
    wire: str,
    value: str,
) -> Mutation:
    return Mutation(id_, expect, fired, edits=(Edit(old, new),), values={wire: value})


def _repriced(
    id_: str, expect: Decision, fired: dict[str, RuleStatus], qty: int, price: str
) -> Mutation:
    edits, values = reprice(qty, price)
    return Mutation(id_, expect, fired, edits=edits, values=values)


_PENALTY = "3. Delay. Late delivery penalty: 1% of order value for each full week of delay.\n"

MUTATIONS: list[Mutation] = [
    _repriced("price_over_3_1pct", REJECT, {"R1": FAIL}, 12_000, "494.88"),
    _one("advance_21pct", REJECT, {"R2": FAIL}, "10% advance", "21% advance", "advance_pct", "21%"),
    Mutation(
        "tin_removed",
        REJECT,
        {"R4": FAIL},
        edits=(Edit("TIN: 101458013391 ", ""),),
        values={"tin": None},
    ),
    Mutation(
        "bin_removed",
        REJECT,
        {"R4": FAIL},
        edits=(Edit(" BIN: 000170141-0101", ""),),
        values={"bin": None},
    ),
    _one(
        "delivery_46_days",
        REJECT,
        {"R5": FAIL},
        "within 24 days of receiving",
        "within 46 days of receiving",
        "delivery_days",
        "46 days",
    ),
    _one(
        "delivery_40_days",
        PERSON,
        {"H4": FAIL},
        "within 24 days of receiving",
        "within 40 days of receiving",
        "delivery_days",
        "40 days",
    ),
    _repriced("quantity_minus_6pct", PERSON, {"H2": FAIL}, 11_280, "472.00"),
    Mutation(
        "penalty_clause_removed",
        REJECT,
        {"R3": FAIL},
        edits=(Edit(_PENALTY, ""),),
        values={"penalty_pct_per_week": None},
    ),
    _one(
        "penalty_0_4pct",
        REJECT,
        {"R3": FAIL},
        "penalty: 1% of order value",
        "penalty: 0.4% of order value",
        "penalty_pct_per_week",
        "0.4%",
    ),
    Mutation(
        "vat_line_removed",
        PERSON,
        {"H5": UNKNOWN, "H6": UNKNOWN},
        edits=(Edit("VAT 15% 849,600.00\n", ""),),
        values={"vat_amount": None},
    ),
    _one(
        "subtotal_off_by_1",
        PERSON,
        {"H5": FAIL, "H6": FAIL},
        "Subtotal 5,664,000.00",
        "Subtotal 5,664,001.00",
        "subtotal",
        "5,664,001.00",
    ),
    _one(
        "validity_29_days",
        PERSON,
        {"H7": FAIL},
        "valid for 45 days",
        "valid for 29 days",
        "validity_days",
        "29 days",
    ),
    _one(
        "payment_61_days",
        PERSON,
        {"H3": FAIL},
        "within 45 days after",
        "within 61 days after",
        "payment_days",
        "61 days",
    ),
]

TWINS: list[Mutation] = [
    _repriced("price_plus_3_00pct_is_H1_not_R1", PERSON, {"H1": FAIL}, 12_000, "494.40"),
    _one("advance_20pct", APPROVE, {}, "10% advance", "20% advance", "advance_pct", "20%"),
    _repriced("quantity_minus_5_0pct", APPROVE, {}, 11_400, "472.00"),
    _one(
        "penalty_0_5pct",
        APPROVE,
        {},
        "penalty: 1% of order value",
        "penalty: 0.5% of order value",
        "penalty_pct_per_week",
        "0.5%",
    ),
    _one(
        "validity_30_days",
        APPROVE,
        {},
        "valid for 45 days",
        "valid for 30 days",
        "validity_days",
        "30 days",
    ),
    _one(
        "payment_60_days",
        APPROVE,
        {},
        "within 45 days after",
        "within 60 days after",
        "payment_days",
        "60 days",
    ),
    _one(
        "delivery_30_days",
        APPROVE,
        {},
        "within 24 days of receiving",
        "within 30 days of receiving",
        "delivery_days",
        "30 days",
    ),
]

CONTROLS: list[Mutation] = [
    Mutation(
        "supplier_renamed",
        APPROVE,
        {},
        edits=(Edit("Padma Textile Mills Ltd", "Padma Textiles Ltd", count=2),),
        values={"supplier": "Padma Textiles Ltd"},
    ),
    Mutation("blank_lines_added", APPROVE, {}, transform=lambda t: t.replace("\n", "\n\n")),
]

# Whitespace noise the PDF reader would not normally produce. The ingest node folds it before any
# reader sees the text, so each must give exactly the original verdict.
WHITESPACE_PROBES: list[Mutation] = [
    Mutation("spaces_widened", APPROVE, {}, transform=lambda t: t.replace(" ", "  ")),
    Mutation("tabs_for_spaces", APPROVE, {}, transform=lambda t: t.replace(" ", "\t")),
    Mutation("crlf_line_endings", APPROVE, {}, transform=lambda t: t.replace("\n", "\r\n")),
    Mutation("trailing_spaces", APPROVE, {}, transform=lambda t: t.replace("\n", "   \n")),
]


def _ids(cases: list[Mutation]) -> list[str]:
    return [m.id for m in cases]


@pytest.mark.parametrize("m", MUTATIONS, ids=_ids(MUTATIONS))
def test_mutation_reaches_the_expected_verdict_through_the_expected_rule(m: Mutation) -> None:
    state = run_mutant(m)
    assert state["errors"] == []
    assert state["verdict"].decision is m.expect, state["verdict"].reason
    assert non_pass(state) == m.fired


@pytest.mark.parametrize("m", TWINS, ids=_ids(TWINS))
def test_just_inside_the_boundary_does_not_flip_the_verdict(m: Mutation) -> None:
    state = run_mutant(m)
    assert state["errors"] == []
    assert state["verdict"].decision is m.expect, state["verdict"].reason
    assert non_pass(state) == m.fired


@pytest.mark.parametrize("m", CONTROLS, ids=_ids(CONTROLS))
def test_control_changes_leave_the_verdict_alone(m: Mutation) -> None:
    state = run_mutant(m)
    assert state["errors"] == []
    assert state["verdict"].decision is APPROVE, state["verdict"].reason
    assert non_pass(state) == {}


@pytest.mark.parametrize("m", MUTATIONS, ids=_ids(MUTATIONS))
def test_a_changed_document_with_the_old_extraction_is_refused(m: Mutation) -> None:
    """Grounding: the recorded quotes no longer exist in the text, so nothing may be trusted."""
    stale_fields = unverifiable_fields(m)
    assert stale_fields, "the edit must invalidate at least one recorded quote"
    state = run_mutant(m, stale=True)
    assert state["errors"] == []
    assert state["verdict"].decision is PERSON, state["verdict"].reason
    for name in stale_fields:
        assert getattr(state["extraction"], name).status is FieldStatus.UNVERIFIED, name


@pytest.mark.parametrize("m", WHITESPACE_PROBES, ids=_ids(WHITESPACE_PROBES))
def test_whitespace_noise_leaves_the_original_verdict(m: Mutation) -> None:
    state = run_mutant(m)
    assert state["errors"] == []
    assert state["verdict"].decision is APPROVE, state["verdict"].reason
    assert non_pass(state) == {}


def _noisy(m: Mutation) -> Mutation:
    def noise(t: str) -> str:
        return t.replace(" ", "\t\t").replace("\n", "  \r\n")

    return replace(m, id=f"{m.id}[noisy]", transform=noise)


@pytest.mark.parametrize("m", [_noisy(x) for x in MUTATIONS], ids=lambda m: m.id)
def test_noise_never_hides_a_real_edit(m: Mutation) -> None:
    """Normalising layout must not mask a changed number: the edit's verdict and rules hold."""
    state = run_mutant(m)
    assert state["errors"] == []
    assert state["verdict"].decision is m.expect, state["verdict"].reason
    assert non_pass(state) == m.fired


# -- safety invariant ---------------------------------------------------------------------


def _every_run() -> list[tuple[str, Decision, Mutation, bool]]:
    runs: list[tuple[str, Decision, Mutation, bool]] = []
    for m in [*MUTATIONS, *TWINS, *CONTROLS]:
        runs.append((m.id, m.expect, m, False))
    for m in MUTATIONS:  # a stale run describes the same changed document: same true verdict
        runs.append((f"{m.id}[stale]", m.expect, m, True))
    return runs


EVERY_RUN = _every_run()


@pytest.mark.parametrize(
    ("truth", "m", "stale"),
    [(t, m, s) for _, t, m, s in EVERY_RUN],
    ids=[i for i, *_ in EVERY_RUN],
)
def test_never_approves_a_document_whose_true_verdict_is_not_approve(
    truth: Decision, m: Mutation, stale: bool
) -> None:
    decision = run_mutant(m, stale=stale)["verdict"].decision
    assert not (decision is APPROVE and truth is not APPROVE)


def test_the_suite_covers_every_required_mutation() -> None:
    required = {
        "price_over_3_1pct", "advance_21pct", "tin_removed", "bin_removed", "delivery_46_days",
        "delivery_40_days", "quantity_minus_6pct", "penalty_clause_removed", "penalty_0_4pct",
        "vat_line_removed", "subtotal_off_by_1", "validity_29_days", "payment_61_days",
    }  # fmt: skip
    assert {m.id for m in MUTATIONS} == required
    assert len(EVERY_RUN) == len(MUTATIONS) * 2 + len(TWINS) + len(CONTROLS)


def test_the_mutations_really_are_not_the_original_document() -> None:
    """Guards the guard: every mutation changes the text, so none can pass by being a no-op."""
    original = mutated_inputs(Mutation("same", APPROVE, {}))[0]
    for m in MUTATIONS:
        assert mutated_inputs(m)[0] != original, m.id
    assert (
        run_inputs(original, mutated_inputs(Mutation("same", APPROVE, {}))[1])["verdict"].decision
        is APPROVE
    )
