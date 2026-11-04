# ruff: noqa: RUF001  (typographic dashes and quotes are the point of this module)
"""Quote verification: no verified quote, no value. Pure functions, no fuzzy matching."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import replace

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
