"""The reason text. Templated from structured findings: no LLM, so it cannot alter a verdict.

Reject: the first failing R rule (the company's listed order, not a severity ranking) leads,
then other rejections, review flags and checks that could not be made.
"""

from __future__ import annotations

from collections.abc import Sequence

from docgate.domain.config import RuleConfig
from docgate.domain.models import Decision, NodeError, RuleResult, RuleStatus, Verdict
from docgate.rules.titles import rule_titles


def _line(result: RuleResult, titles: dict[str, str]) -> str:
    title = titles.get(result.rule_id, "")
    text = f"{result.rule_id} ({title}): {result.message}" if title else result.message
    if result.evidence_quote:
        return f'{text} [evidence: "{result.evidence_quote}"]'
    if result.status is RuleStatus.FAIL:
        return f"{text} [evidence: not found in the document]"
    return text


def _join(label: str, results: Sequence[RuleResult], titles: dict[str, str]) -> str | None:
    if not results:
        return None
    return f"{label}: " + "; ".join(_line(r, titles) for r in results) + "."


def sections(verdict: Verdict, errors: Sequence[NodeError], cfg: RuleConfig) -> list[str]:
    if errors:
        steps = "; ".join(f"{e.node}: {e.message}" for e in errors)
        return [f"A person must check: processing failed ({steps})."]
    titles = rule_titles(cfg)
    rules = verdict.rule_results
    reject = [r for r in rules if r.rule_id.startswith("R") and r.status is RuleStatus.FAIL]
    flagged = [r for r in rules if r.rule_id.startswith("H") and r.status is RuleStatus.FAIL]
    unknown = [r for r in rules if r.status is RuleStatus.UNKNOWN]
    parts: list[str | None]
    if verdict.decision is Decision.REJECT and reject:
        parts = [
            f"Rejected because {_line(reject[0], titles)}.",
            _join("Also rejected by", reject[1:], titles),
            _join("Also flagged", flagged, titles),
            _join("Could not be checked", unknown, titles),
        ]
    elif verdict.decision is Decision.NEEDS_PERSON:
        parts = [
            _join("A person must check", flagged, titles)
            or "A person must check: some checks could not be made.",
            _join("Could not be checked", unknown, titles),
        ]
    else:
        parts = [f"All {len(rules)} checks passed."]
    return [p for p in parts if p]


def explain(verdict: Verdict, errors: Sequence[NodeError], cfg: RuleConfig) -> str:
    return " ".join(sections(verdict, errors, cfg))


def headline(verdict: Verdict, errors: Sequence[NodeError], cfg: RuleConfig) -> str:
    """The first sentence only: what the summary table shows."""
    return sections(verdict, errors, cfg)[0]
