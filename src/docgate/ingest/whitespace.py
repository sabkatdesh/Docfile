"""One canonical spelling of layout whitespace, applied once at ingest.

Why: the regex reader is literal about spacing, quote verification is not. Folding layout noise
before either runs means the LLM, the regex reader and quote checking all see identical text.
Only layout is touched: never digits, punctuation, case, or the single line breaks that separate
fields and table rows. Pure function, idempotent.
"""

from __future__ import annotations

import re

_HORIZONTAL_RUN = re.compile(r"[ \t]+")
_EDGE_SPACE = re.compile(r"(?m)^[ \t]+|[ \t]+$")
_BLANK_RUN = re.compile(r"\n{3,}")


def normalise_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HORIZONTAL_RUN.sub(" ", text)
    text = _EDGE_SPACE.sub("", text)  # after the fold, so a whitespace-only line becomes empty
    return _BLANK_RUN.sub("\n\n", text).strip()
