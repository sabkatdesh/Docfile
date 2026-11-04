"""Run every rule and apply the SPEC precedence. This is the only place a verdict is made."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from docgate.domain.config import DEFAULT_CONFIG, RuleConfig
from docgate.domain.models import Decision, Extraction, PRLine, RuleResult, RuleStatus, Verdict
from docgate.rules.base import Rule, unknown
from docgate.rules.reject import r1_price, r2_advance, r3_penalty, r4_tax_ids, r5_delivery
from docgate.rules.review import (
    h1_price_slightly_over,
    h2_quantity,
    h3_payment,
    h4_delivery_window,
    h5_vat_separate,
    h6_arithmetic,
    h7_validity,
)

RULES: tuple[tuple[str, Rule], ...] = (
    ("R1", r1_price),
    ("R2", r2_advance),
    ("R3", r3_penalty),
    ("R4", r4_tax_ids),
    ("R5", r5_delivery),
    ("H1", h1_price_slightly_over),
    ("H2", h2_quantity),
    ("H3", h3_payment),
    ("H4", h4_delivery_window),
    ("H5", h5_vat_separate),
    ("H6", h6_arithmetic),
    ("H7", h7_validity),
)
EXPECTED_IDS: tuple[str, ...] = tuple(rule_id for rule_id, _ in RULES)


def run_rules(
    ex: Extraction, pr: PRLine | None, cfg: RuleConfig = DEFAULT_CONFIG
) -> list[RuleResult]:
    results: list[RuleResult] = []
    for rule_id, rule in RULES:
        try:
            results.append(rule(ex, pr, cfg))
        except Exception as exc:  # a broken rule must escalate, never crash or approve
            results.append(
                unknown(rule_id, f"rule raised {type(exc).__name__}; a person must check")
            )
    return results


def _normalise(results: Sequence[RuleResult]) -> list[RuleResult]:
    """Exactly one result per expected id; absent or duplicated ids become UNKNOWN."""
    counts = Counter(r.rule_id for r in results)
    by_id = {r.rule_id: r for r in results}
    out: list[RuleResult] = []
    for rule_id in EXPECTED_IDS:
        if counts[rule_id] == 1:
            out.append(by_id[rule_id])
        else:
            out.append(unknown(rule_id, f"expected one result, got {counts[rule_id]}"))
    return out


def _summarise(results: Sequence[RuleResult]) -> str:
    return "; ".join(f"{r.rule_id}: {r.message}" for r in results)


def decide(results: Sequence[RuleResult]) -> Verdict:
    rules = _normalise(results)
    reject = [r for r in rules if r.rule_id.startswith("R") and r.status is RuleStatus.FAIL]
    if reject:
        return Verdict(decision=Decision.REJECT, reason=_summarise(reject), rule_results=rules)
    flagged = [r for r in rules if r.status is not RuleStatus.PASS]
    if flagged:
        return Verdict(
            decision=Decision.NEEDS_PERSON, reason=_summarise(flagged), rule_results=rules
        )
    return Verdict(
        decision=Decision.APPROVE, reason="All reject and review rules passed.", rule_results=rules
    )


def evaluate(ex: Extraction, pr: PRLine | None, cfg: RuleConfig = DEFAULT_CONFIG) -> Verdict:
    return decide(run_rules(ex, pr, cfg))
