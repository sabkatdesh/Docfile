"""Combine the two readers. Only agreement on a verified quote becomes OK.

LLM outcome x regex outcome (after quote verification):
  FOUND+FOUND equal      -> OK            FOUND+FOUND different -> CONFLICT
  FOUND+ABSENT / ABSENT+FOUND            -> CONFLICT
  ABSENT+ABSENT                          -> MISSING
  anything with an UNREADABLE side       -> UNVERIFIED (a bad quote is never rescued by the other)
  an extractor that failed outright      -> every field UNVERIFIED, never MISSING
MISSING feeds rules R3/R4 as FAIL, so an outage must not look like "the document lacks it".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from docgate.domain.models import Extraction, Field, FieldStatus
from docgate.extraction.base import Candidate, ExtractorOutput, Outcome, unreadable
from docgate.extraction.quotes import normalise, verify_candidate

_NO_OUTPUT = unreadable("extractor produced no result for this field")


@dataclass(frozen=True)
class FieldIssue:
    """Why a field is not OK, with both sides' claims so a reviewer can see them."""

    field: str
    status: FieldStatus
    reason: str
    llm_value: Any = None
    regex_value: Any = None
    llm_quote: str | None = None
    regex_quote: str | None = None


@dataclass(frozen=True)
class ReconcileResult:
    extraction: Extraction
    issues: list[FieldIssue]


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return normalise(a) == normalise(b)
    return bool(a == b) and type(a) is type(b)


def _decide(name: str, llm: Candidate, rx: Candidate) -> tuple[Field[Any], FieldIssue | None]:
    quote = llm.quote or rx.quote

    def issue(status: FieldStatus, reason: str) -> tuple[Field[Any], FieldIssue]:
        field: Field[Any] = Field(status=status, quote=quote)
        return field, FieldIssue(name, status, reason, llm.value, rx.value, llm.quote, rx.quote)

    if Outcome.UNREADABLE in (llm.outcome, rx.outcome):
        notes = [
            f"{who}: {c.note}"
            for who, c in (("llm", llm), ("regex", rx))
            if c.note and (c.outcome is Outcome.UNREADABLE)
        ]
        return issue(FieldStatus.UNVERIFIED, "; ".join(notes) or "unreadable")
    if llm.outcome is Outcome.ABSENT and rx.outcome is Outcome.ABSENT:
        return Field(status=FieldStatus.MISSING), None
    if llm.outcome is Outcome.FOUND and rx.outcome is Outcome.FOUND:
        if _same(llm.value, rx.value):
            return Field(value=llm.value, quote=llm.quote, status=FieldStatus.OK), None
        return issue(FieldStatus.CONFLICT, "the two extractors read different values")
    who = "llm" if llm.outcome is Outcome.FOUND else "regex"
    return issue(FieldStatus.CONFLICT, f"only {who} found a value; the other says it is absent")


def reconcile(llm: ExtractorOutput, regex: ExtractorOutput, text: str) -> ReconcileResult:
    fields: dict[str, Field[Any]] = {}
    issues: list[FieldIssue] = []
    failure = llm.failure or regex.failure
    for name in Extraction.model_fields:
        if failure:
            fields[name] = Field(status=FieldStatus.UNVERIFIED)
            who = llm.source if llm.failure else regex.source
            issues.append(FieldIssue(name, FieldStatus.UNVERIFIED, f"{who} failed: {failure}"))
            continue
        left = verify_candidate(llm.candidates.get(name, _NO_OUTPUT), text)
        right = verify_candidate(regex.candidates.get(name, _NO_OUTPUT), text)
        fields[name], issue = _decide(name, left, right)
        if issue:
            issues.append(issue)
    return ReconcileResult(Extraction(**fields), issues)
