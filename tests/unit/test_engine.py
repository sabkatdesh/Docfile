import random
from decimal import Decimal

import pytest

from docgate.domain.models import (
    DayRange,
    Decision,
    FieldStatus,
    RuleResult,
    RuleStatus,
)
from docgate.rules import engine
from docgate.rules.engine import EXPECTED_IDS, decide, evaluate, run_rules
from tests.factories import absent, baseline_extraction, ok, pr_line

D = Decimal
A, R, N = Decision.APPROVE, Decision.REJECT, Decision.NEEDS_PERSON


def results_with(**status: RuleStatus) -> list[RuleResult]:
    return [
        RuleResult(rule_id=i, status=status.get(i, RuleStatus.PASS), message=f"{i} msg")
        for i in EXPECTED_IDS
    ]


def test_all_pass_approves() -> None:
    verdict = evaluate(baseline_extraction(), pr_line())
    assert verdict.decision is A
    assert len(verdict.rule_results) == 12


def test_r_fail_beats_h_fail() -> None:
    v = decide(results_with(R5=RuleStatus.FAIL, H5=RuleStatus.FAIL))
    assert v.decision is R
    assert "R5" in v.reason
    assert "H5" not in v.reason


def test_unknown_and_h_fail_need_a_person() -> None:
    assert decide(results_with(R1=RuleStatus.UNKNOWN)).decision is N
    assert decide(results_with(H3=RuleStatus.FAIL)).decision is N
    assert decide(results_with(H3=RuleStatus.UNKNOWN)).decision is N


def test_r_fail_beats_r_unknown() -> None:
    assert decide(results_with(R1=RuleStatus.UNKNOWN, R5=RuleStatus.FAIL)).decision is R


def test_missing_rule_result_never_approves() -> None:
    partial = results_with()[1:]
    assert decide(partial).decision is N
    assert decide([]).decision is N


def test_duplicate_rule_result_never_approves() -> None:
    doubled = [*results_with(), RuleResult(rule_id="R1", status=RuleStatus.PASS, message="again")]
    assert decide(doubled).decision is N


def test_rule_exception_becomes_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: object) -> RuleResult:
        raise RuntimeError("bug")

    patched = (("R1", boom), *engine.RULES[1:])
    monkeypatch.setattr(engine, "RULES", patched)
    results = run_rules(baseline_extraction(), pr_line())
    assert results[0].rule_id == "R1"
    assert results[0].status is RuleStatus.UNKNOWN
    assert decide(results).decision is N


def test_approve_iff_all_pass() -> None:
    rng = random.Random(0)
    statuses = list(RuleStatus)
    for _ in range(5000):
        picked = {i: rng.choice(statuses) for i in EXPECTED_IDS}
        # bias toward mostly-PASS so Approve cases occur
        if rng.random() < 0.3:
            picked = {i: RuleStatus.PASS for i in EXPECTED_IDS}
        v = decide(results_with(**picked))
        all_pass = all(s is RuleStatus.PASS for s in picked.values())
        any_r_fail = any(s is RuleStatus.FAIL for i, s in picked.items() if i.startswith("R"))
        assert (v.decision is A) == all_pass
        assert (v.decision is R) == any_r_fail
        assert (v.decision is N) == (not all_pass and not any_r_fail)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"price": "103.00"}, N),
        ({"price": "103.01"}, R),
        ({"qty": "21020"}, N),
        ({"qty": "21000"}, A),
        ({"advance_pct": ok(D("20"), "20% advance")}, A),
        ({"advance_pct": ok(D("20.1"), "20.1% advance")}, R),
        ({"tin": absent()}, R),
        ({"delivery_days": ok(30, "30 days")}, A),
        ({"delivery_days": ok(31, "31 days")}, N),
        ({"delivery_days": ok(45, "45 days")}, N),
        ({"delivery_days": ok(46, "46 days")}, R),
        ({"validity_days": ok(30, "30 days")}, A),
        ({"validity_days": ok(29, "29 days")}, N),
        ({"penalty_pct_per_week": ok(D("0.5"), "0.5%")}, A),
        ({"penalty_pct_per_week": ok(D("0.49"), "0.49%")}, R),
        ({"payment_days": ok(DayRange(min=30, max=90), "30 to 90")}, N),
        ({"payment_days": ok(DayRange(min=61, max=61), "61")}, N),
        ({"subtotal": ok(D("1.00"), "s")}, N),
        ({"unit_price": absent(FieldStatus.UNVERIFIED)}, N),
        ({"advance_pct": absent(FieldStatus.CONFLICT)}, N),
    ],
)
def test_single_field_flips(overrides: dict[str, object], expected: Decision) -> None:
    kwargs = dict(overrides)
    price = kwargs.pop("price", "100.00")
    qty = kwargs.pop("qty", "20000")
    ex = baseline_extraction(price=str(price), qty=str(qty), **kwargs)  # type: ignore[arg-type]
    assert evaluate(ex, pr_line()).decision is expected


def test_unknown_pr_line_never_approves() -> None:
    assert evaluate(baseline_extraction(), None).decision is N
