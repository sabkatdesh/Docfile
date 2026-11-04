"""M1 done-when: hand-written fixtures for all 10 packs yield the golden verdicts."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from docgate.compare.pr import find_pr_line
from docgate.domain.models import Decision, Extraction, Field, RuleStatus
from docgate.ingest.pdf import extract_text
from docgate.ingest.purchase_request import load_pr_lines
from docgate.rules.engine import EXPECTED_IDS, evaluate
from tests.fixtures.packs import PACKS
from tests.golden.expected import EXPECTED_NON_PASS, GOLDEN

SAMPLE = Path(__file__).parents[2] / "data" / "sample"
PR_LINES = load_pr_lines(SAMPLE / "purchase-request.csv")
PACK_NUMBERS = sorted(PACKS)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@pytest.mark.parametrize("n", PACK_NUMBERS)
def test_golden_verdict(n: int) -> None:
    ex = PACKS[n]
    verdict = evaluate(ex, find_pr_line(ex, PR_LINES))
    assert verdict.decision is GOLDEN[n], verdict.reason


@pytest.mark.parametrize("n", PACK_NUMBERS)
def test_rule_vector(n: int) -> None:
    ex = PACKS[n]
    results = {r.rule_id: r.status for r in evaluate(ex, find_pr_line(ex, PR_LINES)).rule_results}
    expected = {i: EXPECTED_NON_PASS[n].get(i, RuleStatus.PASS) for i in EXPECTED_IDS}
    assert results == expected


def test_totals_and_no_unsafe_errors() -> None:
    decisions = {n: evaluate(PACKS[n], find_pr_line(PACKS[n], PR_LINES)).decision for n in PACKS}
    unsafe = [n for n, d in decisions.items() if d is Decision.APPROVE and GOLDEN[n] is not d]
    assert unsafe == []
    assert Counter(decisions.values()) == {
        Decision.APPROVE: 2,
        Decision.REJECT: 5,
        Decision.NEEDS_PERSON: 3,
    }


def _ok_quotes(ex: Extraction) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name in Extraction.model_fields:
        f: Field[object] = getattr(ex, name)
        if f.is_ok and f.quote:
            out.append((name, f.quote))
    return out


@pytest.mark.parametrize("n", PACK_NUMBERS)
def test_fixture_quotes_exist_in_pdf(n: int) -> None:
    # Guards the hand-written fixtures only; M2 owns real quote verification.
    text = _norm(extract_text(SAMPLE / f"supplier-pack-{n:02d}.pdf"))
    for name, quote in _ok_quotes(PACKS[n]):
        assert _norm(quote) in text, f"pack {n} {name}: {quote!r}"


def test_pack09_evidence_is_the_arithmetic_error() -> None:
    ex = PACKS[9]
    verdict = evaluate(ex, find_pr_line(ex, PR_LINES))
    h6 = next(r for r in verdict.rule_results if r.rule_id == "H6")
    assert h6.evidence_quote is not None
    assert "322,000.00" in h6.evidence_quote
