"""Independent rule-based reader for the sample quotation template.

It says ABSENT only when the clause or keyword is not in the document, and UNREADABLE whenever the
anchor is there but the value cannot be read unambiguously. It never falls back to a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from docgate.domain.config import DEFAULT_CONFIG, RuleConfig
from docgate.domain.models import Extraction
from docgate.extraction.base import Candidate, ExtractorOutput, absent, found, unreadable
from docgate.extraction.derive import derive_vat_flag
from docgate.extraction.parsing import FIELD_PARSERS, ParseError

_AMOUNT = r"(\d[\d,]*\.\d{2})"
_DURATION = r"(\d+\s+(?:days?|weeks?))"
_HEADING = re.compile(r"\b\d+\. ([A-Z][a-z]+)\. ")
_ITEM_ROW = re.compile(
    rf"^([A-Z])\s+(.+?)\s+(\d[\d,]*)\s+([A-Za-z]+)\s+{_AMOUNT}\s+{_AMOUNT}$", re.MULTILINE
)
_SENTENCE_SPLIT = re.compile(r"(?<=\.)\s+")
_TAX_INCLUSIVE = re.compile(
    r"all taxes included|VAT[ -]?(?:included|inclusive)|inclusive of (?:VAT|taxes)", re.IGNORECASE
)
_PENALTY_HEADINGS = ("delay", "penalty", "penalties")


@dataclass(frozen=True)
class _Clause:
    heading: str
    sentences: tuple[str, ...]

    @property
    def body(self) -> str:
        return " ".join(self.sentences)


def _clauses(text: str) -> list[_Clause]:
    flat = " ".join(text.split())
    _, _, tail = flat.partition("TERMS AND CONDITIONS")
    marks = list(_HEADING.finditer(tail))
    out: list[_Clause] = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(tail)
        sentences = tuple(s for s in _SENTENCE_SPLIT.split(tail[m.end() : end].strip()) if s)
        out.append(_Clause(m.group(1).lower(), sentences))
    return out


def _clause(clauses: list[_Clause], *headings: str) -> _Clause | None:
    return next((c for c in clauses if c.heading in headings), None)


class RegexExtractor:
    name = "regex"

    def __init__(self, cfg: RuleConfig = DEFAULT_CONFIG) -> None:
        self._cfg = cfg

    def extract(self, text: str, label: str = "") -> ExtractorOutput:
        if "QUOTATION" not in text or "TERMS AND CONDITIONS" not in text:
            why = "document does not match the known quotation template"
            return ExtractorOutput(
                source=self.name, candidates={n: unreadable(why) for n in Extraction.model_fields}
            )
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        clauses = _clauses(text)
        c = self._header_fields(text, lines) | self._item_fields(text) | self._money(lines)
        c |= self._terms(clauses) | self._ids(text)
        incl = self._tax_inclusive(lines)
        c["vat_shown_separately"] = derive_vat_flag(c["vat_amount"], incl)
        return ExtractorOutput(source=self.name, candidates=c)

    # -- helpers -------------------------------------------------------------------------

    def _claim(self, name: str, raw: str, quote: str) -> Candidate:
        try:
            value = FIELD_PARSERS[name](raw, self._cfg)
        except ParseError as exc:
            return unreadable(str(exc), quote)
        return found(value, quote, raw=raw)

    def _unique(self, name: str, hits: list[tuple[str, str]], missing: Candidate) -> Candidate:
        """hits are (raw, quote). One distinct parsed value is FOUND; two different ones are not."""
        if not hits:
            return missing
        claims = [self._claim(name, raw, quote) for raw, quote in hits]
        if any(cl.value is None for cl in claims):
            return next(cl for cl in claims if cl.value is None)
        if len({repr(cl.value) for cl in claims}) > 1:
            return unreadable(f"{len(claims)} different values for {name}", claims[0].quote)
        return claims[0]

    # -- fields ----------------------------------------------------------------------------

    def _header_fields(self, text: str, lines: list[str]) -> dict[str, Candidate]:
        out = {"supplier": self._claim("supplier", lines[0], lines[0])}
        for name, pattern, keyword in (
            ("quotation_no", r"Quotation no\.?\s*(\S+)", "Quotation no"),
            ("date", r"\bDate\s+(\d{4}-\d{2}-\d{2})", "Date"),
        ):
            m = re.search(pattern, text)
            if m:
                out[name] = self._claim(name, m.group(1), m.group(0))
            else:
                out[name] = (
                    unreadable(f"{keyword} present but unreadable")
                    if (keyword in text)
                    else absent()
                )
        return out

    def _item_fields(self, text: str) -> dict[str, Candidate]:
        rows = list(_ITEM_ROW.finditer(text))
        names = ("item_code", "description", "qty", "unit", "unit_price")
        if len(rows) != 1:
            why = "no item row found" if not rows else "more than one item row (unsupported)"
            return {n: unreadable(why) for n in names}
        m = rows[0]
        raws = (m.group(1), m.group(2), m.group(3), m.group(4), m.group(5))
        return {n: self._claim(n, raw, m.group(0)) for n, raw in zip(names, raws, strict=True)}

    def _money(self, lines: list[str]) -> dict[str, Candidate]:
        specs = {
            "subtotal": (r"^Subtotal\b", rf"^Subtotal\s+{_AMOUNT}$"),
            "vat_amount": (r"^VAT\b", rf"^VAT\s+\d+(?:\.\d+)?%\s+{_AMOUNT}$"),
            "total": (r"^Total\b", rf"^Total(?:\s*\([^)]*\))?\s+{_AMOUNT}$"),
        }
        out: dict[str, Candidate] = {}
        for name, (anchor, pattern) in specs.items():
            anchored = [ln for ln in lines if re.match(anchor, ln)]
            hits = [(m.group(1), ln) for ln in anchored if (m := re.match(pattern, ln))]
            missing = unreadable(f"{name} line present but unreadable") if anchored else absent()
            out[name] = self._unique(name, hits, missing)
        return out

    def _tax_inclusive(self, lines: list[str]) -> Candidate:
        hits = [ln for ln in lines if _TAX_INCLUSIVE.search(ln)]
        if not hits:
            return absent()
        best = next((ln for ln in hits if ln.startswith("Total")), hits[0])
        return found(True, best)

    def _terms(self, clauses: list[_Clause]) -> dict[str, Candidate]:
        pay = _clause(clauses, "payment")
        deliv = _clause(clauses, "delivery")
        valid = _clause(clauses, "validity")
        return {
            "advance_pct": self._advance(pay),
            "payment_days": self._within(
                "payment_days", pay, r"within\s+(\d+(?:\s+to\s+\d+)?\s+(?:days?|weeks?))"
            ),
            "delivery_days": self._within("delivery_days", deliv, rf"within\s+{_DURATION}"),
            "validity_days": self._within("validity_days", valid, rf"valid for\s+{_DURATION}"),
            "penalty_pct_per_week": self._penalty(clauses),
        }

    def _within(self, name: str, clause: _Clause | None, pattern: str) -> Candidate:
        if clause is None:
            return absent(f"no clause for {name}")
        hits = [(m.group(1), s) for s in clause.sentences for m in re.finditer(pattern, s, re.I)]
        return self._unique(name, hits, unreadable(f"no period found for {name}", clause.body))

    def _advance(self, pay: _Clause | None) -> Candidate:
        if pay is None:
            return absent("no payment clause")
        pct = r"(\d+(?:\.\d+)?\s*%)\s+advance"
        none = r"no advance(?: payment)?(?: required)?"
        hits: list[tuple[str, str]] = []
        for s in pay.sentences:
            hits += [(m.group(1), s) for m in re.finditer(pct, s, re.I)]
            hits += [(m.group(0), s) for m in re.finditer(none, s, re.I)]
        if hits:
            return self._unique("advance_pct", hits, absent())
        if re.search("advance", pay.body, re.I):
            return unreadable("advance mentioned but no percentage found", pay.body)
        return absent("no advance payment statement")

    def _penalty(self, clauses: list[_Clause]) -> Candidate:
        clause = _clause(clauses, *_PENALTY_HEADINGS) or next(
            (c for c in clauses if re.search(r"\bpenalt", c.body, re.I)), None
        )
        if clause is None:
            return absent("no late-delivery penalty clause")
        hits = [
            (m.group(1), s)
            for s in clause.sentences
            for m in re.finditer(r"(\d+(?:\.\d+)?\s*%)", s)
        ]
        return self._unique(
            "penalty_pct_per_week", hits, unreadable("penalty clause has no rate", clause.body)
        )

    def _ids(self, text: str) -> dict[str, Candidate]:
        out: dict[str, Candidate] = {}
        for name, word in (("tin", "TIN"), ("bin", "BIN")):
            hits = [
                (m.group(1), m.group(0))
                for m in re.finditer(rf"\b{word}\b\s*:?\s*(\d[\d-]*)", text)
            ]
            anchored = re.search(rf"\b{word}\b", text) is not None
            missing = unreadable(f"{word} present but unreadable") if anchored else absent()
            out[name] = self._unique(name, hits, missing)
        return out
