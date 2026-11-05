# ruff: noqa: RUF001  (typographic dashes and quotes are the point of this module)
"""Quote verification: no verified quote, no value. Pure functions, no fuzzy matching."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace

from docgate.extraction.base import Candidate, Outcome, unreadable

_DASHES = "‐‑‒–—―−"
_DASH_TABLE = {ord(c): "-" for c in _DASHES}
_QUOTE_TABLE = {ord(c): "'" for c in "‘’‚‛"} | {ord(c): '"' for c in "“”„‟"}
_SPACE = re.compile(r"\s+")
_MIN_QUOTE_LEN = 3
_ELLIPSES = ("...", "…")


def normalise(s: str) -> str:
    """Fold only what PDF extraction or typography changes: spaces, line wraps, dashes, case."""
    s = unicodedata.normalize("NFKC", s).translate(_DASH_TABLE).translate(_QUOTE_TABLE)
    return _SPACE.sub(" ", s).strip().casefold()


def verify_quote(quote: str | None, text: str) -> bool:
    if quote is None:
        return False
    if any(e in quote for e in _ELLIPSES):  # an ellipsis would let the model stitch fragments
        return False
    q = normalise(quote)
    return len(q) >= _MIN_QUOTE_LEN and q in normalise(text)


@dataclass(frozen=True)
class Span:
    """Half-open range of Python string indices into the document text."""

    start: int
    end: int


def _folded_with_origin(text: str) -> tuple[str, list[int]]:
    """`normalise(text)` without the strip, plus the source index of every folded character."""
    out: list[str] = []
    origin: list[int] = []
    for i, ch in enumerate(text):
        folded = unicodedata.normalize("NFKC", ch).translate(_DASH_TABLE).translate(_QUOTE_TABLE)
        for piece in folded.casefold():
            if piece.isspace():
                if out and out[-1] == " ":
                    continue
                piece = " "
            out.append(piece)
            origin.append(i)
    return "".join(out), origin


def locate_quote(quote: str | None, text: str) -> Span | None:
    """Where a quote sits in the text, or None. Same folding as `verify_quote`, so a quote that
    verifies is found even across a line wrap. Never guesses: the span is re-checked, and a
    quote that cannot be placed exactly gets None (the UI then shows the quote without a highlight).
    """
    if quote is None or not verify_quote(quote, text):
        return None
    wanted = normalise(quote)
    folded, origin = _folded_with_origin(text)
    at = folded.find(wanted)
    if at < 0:
        return None
    span = Span(origin[at], origin[at + len(wanted) - 1] + 1)
    return span if normalise(text[span.start : span.end]) == wanted else None


def raw_in_quote(raw: str, quote: str) -> bool:
    """The printed value must appear in the quote as a whole token, not inside another number."""
    r = normalise(raw)
    if not r:
        return False
    pattern = r"(?<![\w.,])" + re.escape(r) + r"(?!\w|[.,]\d)"
    return re.search(pattern, normalise(quote)) is not None


def verify_candidate(cand: Candidate, text: str) -> Candidate:
    """Downgrade a FOUND claim whose evidence does not check out. Other outcomes pass through."""
    if cand.outcome is not Outcome.FOUND:
        return cand
    if not verify_quote(cand.quote, text):
        return replace(unreadable("quote not found in the document text", cand.quote), raw=cand.raw)
    if cand.raw is not None and not raw_in_quote(cand.raw, cand.quote or ""):
        return unreadable(f"value {cand.raw!r} is not in its quote", cand.quote)
    return cand
