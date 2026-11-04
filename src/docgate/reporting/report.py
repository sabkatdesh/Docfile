"""Per-pack and summary reports. Pure: build models from findings, render to JSON or Markdown.

No timestamps and no randomness, so the same inputs give byte-identical files.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from docgate.compare.summary import Comparison
from docgate.domain.config import RuleConfig
from docgate.domain.models import (
    DayRange,
    Decision,
    Extraction,
    NodeError,
    PRLine,
    Verdict,
)
from docgate.extraction.reconcile import FieldIssue
from docgate.reporting.explain import explain, headline
from docgate.rules.titles import rule_titles

SCHEMA_VERSION = 1
_CENT = Decimal("0.01")


class FieldReport(BaseModel):
    name: str
    status: str
    value: str | None
    quote: str | None


class IssueReport(BaseModel):
    field: str
    status: str
    reason: str
    llm_value: str | None
    regex_value: str | None


class RuleReport(BaseModel):
    rule_id: str
    title: str
    status: str
    message: str
    evidence_quote: str | None


class ArithmeticReport(BaseModel):
    check: str
    expected: Decimal | None
    actual: Decimal | None
    ok: bool | None
    quote: str | None


class PackReport(BaseModel):
    schema_version: int = SCHEMA_VERSION
    pack_id: str
    source_file: str
    decision: Decision
    needs_human: bool
    human_decision: Decision | None
    reason: str
    explanation: str
    headline: str
    primary_rule: str | None
    rule_results: list[RuleReport]
    fields: list[FieldReport]
    issues: list[IssueReport]
    pr_line: PRLine | None
    price_delta_pct: Decimal | None
    qty_delta_pct: Decimal | None
    price_note: str | None
    arithmetic: list[ArithmeticReport]
    errors: list[NodeError]


def _show(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, DayRange):
        return f"{value.min}-{value.max} days"
    return str(value)


def _cents(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(_CENT)


def _primary_rule(verdict: Verdict) -> str | None:
    if verdict.decision is Decision.REJECT:
        for r in verdict.rule_results:
            if r.rule_id.startswith("R") and r.status.value == "FAIL":
                return r.rule_id
    return None


def build_report(
    *,
    pack_id: str,
    source_file: str,
    verdict: Verdict,
    extraction: Extraction | None,
    issues: Sequence[FieldIssue],
    comparison: Comparison | None,
    errors: Sequence[NodeError],
    cfg: RuleConfig,
) -> PackReport:
    titles = rule_titles(cfg)
    fields: list[FieldReport] = []
    if extraction is not None:
        for name in Extraction.model_fields:
            f = getattr(extraction, name)
            fields.append(
                FieldReport(name=name, status=f.status.value, value=_show(f.value), quote=f.quote)
            )
    return PackReport(
        pack_id=pack_id,
        source_file=source_file,
        decision=verdict.decision,
        needs_human=verdict.needs_human,
        human_decision=verdict.human_decision,
        reason=verdict.reason,
        explanation=explain(verdict, errors, cfg),
        headline=headline(verdict, errors, cfg),
        primary_rule=_primary_rule(verdict),
        rule_results=[
            RuleReport(
                rule_id=r.rule_id,
                title=titles.get(r.rule_id, ""),
                status=r.status.value,
                message=r.message,
                evidence_quote=r.evidence_quote,
            )
            for r in verdict.rule_results
        ],
        fields=fields,
        issues=[
            IssueReport(
                field=i.field,
                status=i.status.value,
                reason=i.reason,
                llm_value=_show(i.llm_value),
                regex_value=_show(i.regex_value),
            )
            for i in issues
        ],
        pr_line=comparison.pr_line if comparison else None,
        price_delta_pct=_cents(comparison.price_delta_pct) if comparison else None,
        qty_delta_pct=_cents(comparison.qty_delta_pct) if comparison else None,
        price_note=comparison.price_note if comparison else None,
        arithmetic=[
            ArithmeticReport(
                check=a.check, expected=a.expected, actual=a.actual, ok=a.ok, quote=a.quote
            )
            for a in (comparison.arithmetic if comparison else [])
        ],
        errors=list(errors),
    )


def render_json(report: BaseModel) -> str:
    return report.model_dump_json(indent=2) + "\n"


def _cell(text: object) -> str:
    return "" if text is None else str(text).replace("|", "\\|").replace("\n", " ")


def _table(header: list[str], rows: list[list[object]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return lines


def render_markdown(r: PackReport) -> str:
    out = [f"# {r.pack_id}: {r.decision.value}", ""]
    if r.needs_human:
        done = f" Human decision: {r.human_decision.value}." if r.human_decision else ""
        out += [f"**Needs a person to check.**{done}", ""]
    out += [f"**Reason.** {r.explanation}", ""]
    if r.errors:
        out += ["## Errors", ""]
        out += [f"- `{e.node}` ({e.kind}): {e.message}" for e in r.errors] + [""]
    if r.rule_results:
        out += ["## Rules", ""]
        out += [
            *_table(
                ["Rule", "Check", "Status", "Finding", "Evidence"],
                [
                    [x.rule_id, x.title, x.status, x.message, x.evidence_quote]
                    for x in r.rule_results
                ],
            ),
            "",
        ]
    if r.pr_line is not None or r.arithmetic:
        out += ["## Comparison with the purchase request", ""]
        if r.pr_line:
            out += [
                f"- Requested: item {r.pr_line.item_code}, quantity {r.pr_line.qty} "
                f"{r.pr_line.unit}, maximum unit price {r.pr_line.max_unit_price}",
            ]
        price = (
            f"{r.price_delta_pct:+}%" if r.price_delta_pct is not None else f"n/a ({r.price_note})"
        )
        qty = f"{r.qty_delta_pct:+}%" if r.qty_delta_pct is not None else "n/a"
        out += [f"- Price vs maximum: {price}", f"- Quantity vs request: {qty}", ""]
        out += [
            *_table(
                ["Arithmetic check", "Expected", "Quoted", "OK", "Evidence"],
                [[a.check, a.expected, a.actual, a.ok, a.quote] for a in r.arithmetic],
            ),
            "",
        ]
    if r.fields:
        out += ["## Extracted fields", ""]
        out += [
            *_table(
                ["Field", "Status", "Value", "Quote"],
                [[f.name, f.status, f.value, f.quote] for f in r.fields],
            ),
            "",
        ]
    if r.issues:
        out += ["## Extraction issues", ""]
        out += [
            *_table(
                ["Field", "Status", "Reason", "LLM read", "Regex read"],
                [[i.field, i.status, i.reason, i.llm_value, i.regex_value] for i in r.issues],
            ),
            "",
        ]
    return "\n".join(out)


class SummaryRow(BaseModel):
    pack_id: str
    supplier: str | None
    item: str | None
    decision: Decision
    needs_human: bool
    primary_rule: str | None
    top_reason: str


class Summary(BaseModel):
    schema_version: int = SCHEMA_VERSION
    total: int
    counts: dict[str, int]
    rows: list[SummaryRow]


def _field(r: PackReport, name: str) -> str | None:
    return next((f.value for f in r.fields if f.name == name), None)


def build_summary(reports: Sequence[PackReport]) -> Summary:
    ordered = sorted(reports, key=lambda r: r.pack_id)
    counts = Counter(r.decision.value for r in ordered)
    return Summary(
        total=len(ordered),
        counts={d.value: counts[d.value] for d in Decision},
        rows=[
            SummaryRow(
                pack_id=r.pack_id,
                supplier=_field(r, "supplier"),
                item=_field(r, "item_code"),
                decision=r.decision,
                needs_human=r.needs_human,
                primary_rule=r.primary_rule,
                top_reason=r.headline,
            )
            for r in ordered
        ],
    )


def render_summary_markdown(s: Summary) -> str:
    out = [
        "# Run summary",
        "",
        f"{s.total} packs. " + ", ".join(f"{k}: {v}" for k, v in s.counts.items()),
        "",
    ]
    out += _table(
        ["Pack", "Supplier", "Item", "Decision", "Top reason"],
        [[r.pack_id, r.supplier, r.item, r.decision.value, r.top_reason] for r in s.rows],
    )
    return "\n".join(out) + "\n"
