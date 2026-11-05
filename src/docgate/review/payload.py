"""What a paused pack shows its reviewer. Pure: findings in, a JSON-ready model out."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from docgate.domain.config import RuleConfig
from docgate.domain.models import Decision, NodeError, RuleStatus, Verdict
from docgate.extraction.reconcile import FieldIssue
from docgate.rules.titles import rule_titles

QUESTION = "The automatic checks could not settle this pack. Approve or Reject it, with a reason."


class PayloadRule(BaseModel):
    rule_id: str
    title: str
    status: str
    message: str
    evidence_quote: str | None


class PayloadIssue(BaseModel):
    field: str
    status: str
    reason: str
    llm_value: str | None
    regex_value: str | None
    llm_quote: str | None
    regex_quote: str | None


class ReviewPayload(BaseModel):
    pack_id: str
    question: str
    machine_decision: Decision
    reason: str
    rules: list[PayloadRule]
    issues: list[PayloadIssue]
    errors: list[NodeError]


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


def build_payload(
    pack_id: str,
    verdict: Verdict,
    issues: Sequence[FieldIssue],
    errors: Sequence[NodeError],
    cfg: RuleConfig,
) -> ReviewPayload:
    titles = rule_titles(cfg)
    return ReviewPayload(
        pack_id=pack_id,
        question=QUESTION,
        machine_decision=verdict.decision,
        reason=verdict.reason,
        rules=[
            PayloadRule(
                rule_id=r.rule_id,
                title=titles.get(r.rule_id, ""),
                status=r.status.value,
                message=r.message,
                evidence_quote=r.evidence_quote,
            )
            for r in verdict.rule_results
            if r.status is not RuleStatus.PASS
        ],
        issues=[
            PayloadIssue(
                field=i.field,
                status=i.status.value,
                reason=i.reason,
                llm_value=_text(i.llm_value),
                regex_value=_text(i.regex_value),
                llm_quote=i.llm_quote,
                regex_quote=i.regex_quote,
            )
            for i in issues
        ],
        errors=list(errors),
    )
