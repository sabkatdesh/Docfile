"""M2 done-when: all 10 packs extract from the committed recordings, every kept field has a
verified quote, and the result matches the hand-written M1 fixtures (and so the golden verdicts).

Replay only: no key, no network. If a recording is missing, run `python tasks.py record`.
"""

from __future__ import annotations

import socket
from collections import Counter
from pathlib import Path

import pytest

from docgate.compare.pr import find_pr_line
from docgate.domain.models import Extraction, FieldStatus
from docgate.extraction.factory import build_llm_stack
from docgate.extraction.quotes import verify_quote
from docgate.extraction.reconcile import ReconcileResult
from docgate.extraction.regex import RegexExtractor
from docgate.extraction.service import extract_document
from docgate.ingest.pdf import extract_text
from docgate.ingest.purchase_request import load_pr_lines
from docgate.rules.engine import evaluate
from docgate.settings import load_settings
from tests.fixtures.packs import PACKS
from tests.golden.expected import GOLDEN

ROOT = Path(__file__).parents[2]
SAMPLE = ROOT / "data" / "sample"
PR_LINES = load_pr_lines(SAMPLE / "purchase-request.csv")
PACKS_N = sorted(PACKS)


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("replay must never touch the network")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)


def _text(n: int) -> str:
    return extract_text(SAMPLE / f"supplier-pack-{n:02d}.pdf")


def _extract(n: int) -> ReconcileResult:
    settings = load_settings({"DOCGATE_RECORDED_DIR": str(ROOT / "data" / "recorded")})
    stack = build_llm_stack(settings)
    return extract_document(_text(n), f"supplier-pack-{n:02d}", stack.extractor, RegexExtractor())


@pytest.mark.parametrize("n", PACKS_N)
def test_pack_extracts_with_no_issues_other_than_true_absences(n: int) -> None:
    result = _extract(n)
    assert [(i.field, i.status.value, i.reason) for i in result.issues] == []


@pytest.mark.parametrize("n", PACKS_N)
def test_every_kept_field_has_a_verified_quote(n: int) -> None:
    text = _text(n)
    for name in Extraction.model_fields:
        field = getattr(_extract(n).extraction, name)
        if field.status is FieldStatus.OK:
            assert verify_quote(field.quote, text), f"pack {n} {name}: {field.quote!r}"


@pytest.mark.parametrize("n", PACKS_N)
def test_values_match_the_hand_written_fixtures(n: int) -> None:
    got, want = _extract(n).extraction, PACKS[n]
    for name in Extraction.model_fields:
        g, w = getattr(got, name), getattr(want, name)
        assert (g.status, g.value) == (w.status, w.value), f"pack {n} {name}"


@pytest.mark.parametrize("n", PACKS_N)
def test_extraction_feeds_the_rules_to_the_golden_verdict(n: int) -> None:
    ex = _extract(n).extraction
    assert evaluate(ex, find_pr_line(ex, PR_LINES)).decision is GOLDEN[n]


def test_totals_across_all_packs() -> None:
    counts: Counter[FieldStatus] = Counter()
    for n in PACKS_N:
        ex = _extract(n).extraction
        counts.update(getattr(ex, name).status for name in Extraction.model_fields)
    assert counts == {FieldStatus.OK: 185, FieldStatus.MISSING: 5}
