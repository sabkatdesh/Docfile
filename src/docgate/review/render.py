"""Plain-text views of the review queue for the terminal. Pure: models in, string out."""

from __future__ import annotations

from collections.abc import Sequence

from docgate.review.payload import ReviewPayload
from docgate.review.store import PendingReview, ReviewKind, ReviewStatus


def render_pending(items: Sequence[PendingReview]) -> str:
    if not items:
        return "No packs are waiting for a decision."
    lines = [f"{len(items)} pack(s) waiting for a decision:"]
    for item in items:
        why = ", ".join(r.rule_id for r in item.payload.rules) or "processing failed"
        lines.append(f"  {item.pack_id:<20} {why}")
    return "\n".join(lines)


def _payload_lines(p: ReviewPayload) -> list[str]:
    lines = [f"Question: {p.question}", f"Reason: {p.reason}", ""]
    for r in p.rules:
        lines.append(f"  {r.rule_id} {r.status}: {r.title}")
        lines.append(f"      {r.message}")
        lines.append(f"      evidence: {r.evidence_quote or '(no quote)'}")
    for i in p.issues:
        lines.append(f"  field {i.field} {i.status}: {i.reason}")
        lines.append(f"      LLM read: {i.llm_value} ({i.llm_quote})")
        lines.append(f"      regex read: {i.regex_value} ({i.regex_quote})")
    lines += [f"  error in {e.node}: {e.message}" for e in p.errors]
    return lines


def render_status(s: ReviewStatus) -> str:
    machine = s.machine_decision.value if s.machine_decision else "none"
    lines = [f"{s.pack_id}: {s.kind.value}", f"Machine verdict: {machine}"]
    if s.kind is ReviewKind.PENDING and s.payload is not None:
        lines += _payload_lines(s.payload)
    if s.human_review is not None:
        h = s.human_review
        lines += [
            f"Human decision: {h.decision.value}",
            f"Reason: {h.reason}",
            f"Reviewer: {h.reviewer}",
            f"Reviewed at: {h.reviewed_at.isoformat()}",
        ]
    return "\n".join(lines)
