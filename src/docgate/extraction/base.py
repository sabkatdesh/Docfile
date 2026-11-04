"""Types shared by every extractor. An extractor proposes; quotes.py and reconcile.py decide."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class Outcome(StrEnum):
    FOUND = "FOUND"  # a value with a quote
    ABSENT = "ABSENT"  # the document does not state it
    UNREADABLE = "UNREADABLE"  # stated, but cannot be read reliably (or the claim failed checks)


@dataclass(frozen=True)
class Candidate:
    """One extractor's claim about one field. `raw` is the value exactly as printed."""

    outcome: Outcome
    value: Any = None
    quote: str | None = None
    raw: str | None = None
    note: str | None = None


def found(value: Any, quote: str, raw: str | None = None) -> Candidate:
    return Candidate(Outcome.FOUND, value=value, quote=quote, raw=raw)


def absent(note: str = "not stated in the document") -> Candidate:
    return Candidate(Outcome.ABSENT, note=note)


def unreadable(note: str, quote: str | None = None) -> Candidate:
    return Candidate(Outcome.UNREADABLE, quote=quote, note=note)


@dataclass(frozen=True)
class ExtractorOutput:
    """`failure` set means the extractor produced nothing usable; candidates are then empty."""

    source: str
    candidates: Mapping[str, Candidate] = field(default_factory=dict)
    failure: str | None = None


class Extractor(Protocol):
    name: str

    def extract(self, text: str, label: str = "") -> ExtractorOutput: ...
