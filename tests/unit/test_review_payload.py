"""The reviewer must see why a pack paused without opening the PDF."""

from __future__ import annotations

from docgate.domain.config import DEFAULT_CONFIG
from docgate.domain.models import Decision, FieldStatus, NodeError
from docgate.extraction.reconcile import FieldIssue
from docgate.review.payload import ReviewPayload, build_payload
from docgate.rules.engine import escalate
from docgate.workflow.graph import build_graph, run_pack
from tests.graph_support import pack_path, replay_deps


def _state(n: int) -> dict[str, object]:
    return dict(run_pack(build_graph(replay_deps()), f"supplier-pack-{n:02d}", pack_path(n)))


def _payload(n: int) -> ReviewPayload:
    s = _state(n)
    return build_payload(
        f"supplier-pack-{n:02d}",
        s["verdict"],  # type: ignore[arg-type]
        s.get("issues", []),  # type: ignore[arg-type]
        s.get("errors", []),  # type: ignore[arg-type]
        DEFAULT_CONFIG,
    )


def test_payload_lists_only_non_pass_rules_with_quotes() -> None:
    p = _payload(9)
    assert {r.rule_id for r in p.rules} == {"H3", "H6"}
    assert all(r.status != "PASS" for r in p.rules)
    h6 = next(r for r in p.rules if r.rule_id == "H6")
    assert "322,000" in (h6.evidence_quote or "")
    assert h6.title == "Numbers do not add up"


def test_payload_states_question_machine_verdict_and_pack() -> None:
    p = _payload(4)
    assert p.pack_id == "supplier-pack-04"
    assert p.machine_decision is Decision.NEEDS_PERSON
    assert "Approve or Reject" in p.question
    assert [r.rule_id for r in p.rules] == ["H1"]
    assert p.errors == []


def test_payload_includes_both_reads_for_a_conflict() -> None:
    issue = FieldIssue(
        field="unit_price",
        status=FieldStatus.CONFLICT,
        reason="extractors disagree",
        llm_value="6.50",
        regex_value="6.05",
        llm_quote="Unit price 6.50",
        regex_quote="Unit price 6.05",
    )
    verdict = escalate("conflict")
    p = build_payload("p", verdict, [issue], [], DEFAULT_CONFIG)
    assert len(p.issues) == 1
    got = p.issues[0]
    assert (got.field, got.llm_value, got.regex_value) == ("unit_price", "6.50", "6.05")
    assert (got.llm_quote, got.regex_quote) == ("Unit price 6.50", "Unit price 6.05")


def test_payload_for_escalated_pack_includes_errors() -> None:
    err = NodeError(node="ingest", kind="error", message="EmptyPdfError: no text")
    p = build_payload("p", escalate("Processing failed"), [], [err], DEFAULT_CONFIG)
    assert p.rules == []
    assert [(e.node, e.message) for e in p.errors] == [("ingest", "EmptyPdfError: no text")]


def test_payload_round_trips_through_json() -> None:
    p = _payload(7)
    assert ReviewPayload.model_validate(p.model_dump(mode="json")) == p
