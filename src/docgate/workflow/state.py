"""Typed graph state. Dependencies (extractors, config) are not in here, so the state stays
serializable for the checkpointer that M4 adds."""

from __future__ import annotations

import operator
from collections.abc import Sequence
from typing import Annotated, TypedDict

from docgate.compare.summary import Comparison
from docgate.domain.models import Extraction, NodeError, RuleResult, Verdict
from docgate.extraction.base import ExtractorOutput
from docgate.extraction.reconcile import FieldIssue
from docgate.reporting.report import PackReport


class PackState(TypedDict, total=False):
    pack_id: str
    pdf_path: str
    text: str
    llm_out: ExtractorOutput
    regex_out: ExtractorOutput
    extraction: Extraction
    issues: list[FieldIssue]
    comparison: Comparison
    rule_results: list[RuleResult]
    verdict: Verdict
    report: PackReport
    # Both extractors can fail in the same step, so errors are appended, not overwritten.
    errors: Annotated[list[NodeError], operator.add]


def describe_errors(errors: Sequence[NodeError]) -> str:
    parts = "; ".join(f"{e.node}: {e.message}" for e in errors)
    return f"Processing failed ({parts}); a person must check"
