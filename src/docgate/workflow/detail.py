"""What the API shows for one pack. Pure mapping from a pack's state to JSON-ready models.

No judging happens here: verdicts, rule results and deltas are copied from the state; the only
thing computed is where each verified quote sits in the text (for highlighting).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from docgate.domain.config import DEFAULT_CONFIG, RuleConfig
from docgate.domain.models import Decision, HumanReview, NodeError, PRLine
from docgate.extraction.quotes import locate_quote
from docgate.reporting.report import IssueReport, PackReport
from docgate.workflow.runner import report_of
from docgate.workflow.state import PackState

PackStatus = Literal["not_run", "pending_review", "resolved", "final"]


class TextSpan(BaseModel):
    """Half-open range of Python string indices into `PackDetail.text`. The sample texts are
    ASCII, where these equal JavaScript (UTF-16) offsets."""

    start: int
    end: int


class FieldDetail(BaseModel):
    name: str
    status: str
    value: str | None
    quote: str | None
    span: TextSpan | None
    issue: str | None


class RuleDetail(BaseModel):
    rule_id: str
    title: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    message: str
    evidence_quote: str | None
    span: TextSpan | None


class ArithmeticDetail(BaseModel):
    check: str
    expected: Decimal | None
    actual: Decimal | None
    ok: bool | None
    quote: str | None
    span: TextSpan | None


class ComparisonDetail(BaseModel):
    pr_line: PRLine | None
    requested_qty: Decimal | None
    quoted_qty: Decimal | None
    qty_delta_pct: Decimal | None
    max_unit_price: Decimal | None
    quoted_unit_price: Decimal | None
    price_delta_pct: Decimal | None
    price_note: str | None
    arithmetic: list[ArithmeticDetail]


class MachineVerdict(BaseModel):
    decision: Decision
    reason: str
    headline: str
    explanation: str
    primary_rule: str | None
    needs_human: bool


class PackDetail(BaseModel):
    pack_id: str
    source_file: str
    pdf_url: str
    status: PackStatus
    text: str
    machine: MachineVerdict
    human_review: HumanReview | None
    fields: list[FieldDetail]
    comparison: ComparisonDetail | None
    rules: list[RuleDetail]
    issues: list[IssueReport]
    errors: list[NodeError]


class PackListItem(BaseModel):
    pack_id: str
    source_file: str
    supplier: str | None
    item: str | None
    status: PackStatus
    decision: Decision | None
    human_decision: Decision | None
    primary_rule: str | None
    headline: str | None


def pack_status(state: PackState | None) -> PackStatus:
    if state is None or "verdict" not in state:
        return "not_run"
    if "report" not in state:
        return "pending_review"  # parked at the human gate; the final report is written after it
    return "resolved" if state["verdict"].human_review else "final"


def _span(quote: str | None, text: str) -> TextSpan | None:
    found = locate_quote(quote, text)
    return TextSpan(start=found.start, end=found.end) if found else None


def _value(report: PackReport, name: str) -> str | None:
    return next((f.value for f in report.fields if f.name == name), None)


def _decimal(report: PackReport, name: str) -> Decimal | None:
    raw = _value(report, name)
    return Decimal(raw) if raw else None  # fields hold Decimal's own str(), never a float


def _comparison(report: PackReport, text: str) -> ComparisonDetail | None:
    if report.pr_line is None and not report.arithmetic:
        return None
    pr = report.pr_line
    return ComparisonDetail(
        pr_line=pr,
        requested_qty=pr.qty if pr else None,
        quoted_qty=_decimal(report, "qty"),
        qty_delta_pct=report.qty_delta_pct,
        max_unit_price=pr.max_unit_price if pr else None,
        quoted_unit_price=_decimal(report, "unit_price"),
        price_delta_pct=report.price_delta_pct,
        price_note=report.price_note,
        arithmetic=[
            ArithmeticDetail(
                check=a.check,
                expected=a.expected,
                actual=a.actual,
                ok=a.ok,
                quote=a.quote,
                span=_span(a.quote, text),
            )
            for a in report.arithmetic
        ],
    )


def build_detail(state: PackState, cfg: RuleConfig = DEFAULT_CONFIG) -> PackDetail:
    report = report_of(state, cfg)
    text = state.get("text", "")
    reasons = {i.field: i.reason for i in report.issues}
    return PackDetail(
        pack_id=report.pack_id,
        source_file=report.source_file,
        pdf_url=f"/api/packs/{report.pack_id}/pdf",
        status=pack_status(state),
        text=text,
        machine=MachineVerdict(
            decision=report.decision,
            reason=report.reason,
            headline=report.headline,
            explanation=report.explanation,
            primary_rule=report.primary_rule,
            needs_human=report.needs_human,
        ),
        human_review=report.human_review,
        fields=[
            FieldDetail(
                name=f.name,
                status=f.status,
                value=f.value,
                quote=f.quote,
                span=_span(f.quote, text),
                issue=reasons.get(f.name),
            )
            for f in report.fields
        ],
        comparison=_comparison(report, text),
        rules=[
            RuleDetail.model_validate({**r.model_dump(), "span": _span(r.evidence_quote, text)})
            for r in report.rule_results
        ],
        issues=report.issues,
        errors=report.errors,
    )


def build_list_item(pack_id: str, source_file: str, state: PackState | None) -> PackListItem:
    if state is None or "verdict" not in state:
        return PackListItem(
            pack_id=pack_id,
            source_file=source_file,
            supplier=None,
            item=None,
            status="not_run",
            decision=None,
            human_decision=None,
            primary_rule=None,
            headline=None,
        )
    report = report_of(state)
    return PackListItem(
        pack_id=pack_id,
        source_file=source_file,
        supplier=_value(report, "supplier"),
        item=_value(report, "item_code"),
        status=pack_status(state),
        decision=report.decision,
        human_decision=report.human_decision,
        primary_rule=report.primary_rule,
        headline=report.headline,
    )
