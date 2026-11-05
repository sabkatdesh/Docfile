"""Run a changed copy of a real quotation through the real pipeline, without an API.

The recording key hashes the document text, so replay cannot serve an edited document. Instead a
scripted provider hands the edited *recorded response* to the real `LLMExtractor`. Reconcile,
compare, rules and decide are all the real code; only the PDF read is replaced by the edited text.

Two ways to mutate:
  consistent (default): text, recorded value and recorded quote change together, so quote
      verification passes and the rules see a genuinely different document.
  stale: only the text changes. The recorded extraction still describes the old document, so its
      quotes no longer verify. This proves the grounding: such a field must become UNVERIFIED.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from docgate.domain.models import Decision, RuleStatus
from docgate.extraction.llm import LLMExtractor
from docgate.extraction.prompt import load_prompt
from docgate.extraction.quotes import verify_quote
from docgate.extraction.regex import RegexExtractor
from docgate.ingest.pdf import extract_text
from docgate.settings import Settings, request_params
from docgate.workflow.graph import Deps, build_graph, run_pack
from docgate.workflow.state import PackState
from tests.fakes import FakeProvider
from tests.graph_support import PR_LINES, RECORDED, pack_path

VAT_RATE = Decimal("0.15")


class HarnessError(AssertionError):
    """The mutation itself is malformed; never a statement about the system under test."""


@dataclass(frozen=True)
class Edit:
    """Literal replacement in the document text. `old` must occur exactly `count` times."""

    old: str
    new: str
    count: int = 1


@dataclass(frozen=True)
class Mutation:
    id: str
    expect: Decision
    fired: Mapping[str, RuleStatus]  # exact set of non-PASS rules, e.g. {"R1": RuleStatus.FAIL}
    edits: tuple[Edit, ...] = ()
    # Recorded value per wire field after the change; None means "the document no longer says it".
    values: Mapping[str, str | None] = field(default_factory=dict)
    transform: Callable[[str], str] | None = None  # whitespace-style changes with no edit
    pack: int = 1


def base_text(pack: int) -> str:
    return extract_text(pack_path(pack))


def base_response(pack: int) -> dict[str, Any]:
    path = next(RECORDED.glob(f"supplier-pack-{pack:02d}__*.json"))
    loaded: dict[str, Any] = json.loads(json.loads(path.read_text("utf-8"))["response"])
    return loaded


def apply_edits(text: str, edits: tuple[Edit, ...]) -> str:
    for e in edits:
        found = text.count(e.old)
        if found != e.count:
            raise HarnessError(f"edit {e.old!r} occurs {found} times, expected {e.count}")
        text = text.replace(e.old, e.new)
    return text


def _rewrite_quote(quote: str | None, edits: tuple[Edit, ...]) -> str | None:
    if quote is None:
        return None
    for e in edits:
        quote = quote.replace(e.old, e.new)
    return quote


def mutated_inputs(m: Mutation, *, stale: bool = False) -> tuple[str, dict[str, Any]]:
    """The edited document text and the response the scripted provider will return."""
    text = apply_edits(base_text(m.pack), m.edits)
    if m.transform is not None:
        text = m.transform(text)
    response = base_response(m.pack)
    if stale:
        return text, response  # recorded extraction deliberately left describing the old text
    for name, wire in response.items():
        wire["quote"] = _rewrite_quote(wire["quote"], m.edits)
        if name in m.values:
            wire["value"] = m.values[name]
            if m.values[name] is None:
                wire["quote"] = None
    lost = [n for n, w in response.items() if w["quote"] and not verify_quote(w["quote"], text)]
    if lost:  # a harness bug must not masquerade as the system rejecting the document
        raise HarnessError(f"mutation {m.id}: quotes no longer in the text for {lost}")
    return text, response


def unverifiable_fields(m: Mutation) -> list[str]:
    """Recorded fields whose quote the edited text no longer contains (what stale must catch)."""
    text, response = mutated_inputs(m, stale=True)
    return [n for n, w in response.items() if w["quote"] and not verify_quote(w["quote"], text)]


def run_inputs(text: str, response: dict[str, Any], pack: int = 1) -> PackState:
    provider = FakeProvider([json.dumps(response)])
    llm = LLMExtractor(provider, load_prompt(), request_params(Settings()))
    deps = Deps(llm=llm, regex=RegexExtractor(), pr_lines=PR_LINES, read_text=lambda _p: text)
    return run_pack(build_graph(deps), f"supplier-pack-{pack:02d}", pack_path(pack))


def run_mutant(m: Mutation, *, stale: bool = False) -> PackState:
    text, response = mutated_inputs(m, stale=stale)
    return run_inputs(text, response, m.pack)


def non_pass(state: PackState) -> dict[str, RuleStatus]:
    return {
        r.rule_id: r.status
        for r in state["verdict"].rule_results
        if r.status is not RuleStatus.PASS
    }


# -- repricing pack 01 so only the intended rule moves --------------------------------------

_ORIG_ROW = "12,000 metre 472.00 5,664,000.00"


def _money(d: Decimal) -> str:
    return f"{d:,.2f}"


def reprice(qty: int, price: str) -> tuple[tuple[Edit, ...], dict[str, str | None]]:
    """Pack 01 with a new quantity and unit price and every dependent figure recomputed with
    Decimal (amount, subtotal, 15% VAT, total), so a price or quantity mutation fires only its
    own rule and not the arithmetic checks as a side effect."""
    unit = Decimal(price)
    amount = unit * qty
    vat = amount * VAT_RATE
    total = amount + vat
    edits = (
        Edit(_ORIG_ROW, f"{qty:,} metre {_money(unit)} {_money(amount)}"),
        Edit("Subtotal 5,664,000.00", f"Subtotal {_money(amount)}"),
        Edit("VAT 15% 849,600.00", f"VAT 15% {_money(vat)}"),
        Edit("Total 6,513,600.00", f"Total {_money(total)}"),
    )
    values: dict[str, str | None] = {
        "qty": f"{qty:,}",
        "unit_price": _money(unit),
        "subtotal": _money(amount),
        "vat_amount": _money(vat),
        "total": _money(total),
    }
    return edits, values
