"""Reports are built from structured findings only: no LLM, no clock, byte-identical reruns."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from docgate.domain.config import DEFAULT_CONFIG
from docgate.domain.models import DayRange, Decision
from docgate.reporting.explain import explain
from docgate.reporting.report import (
    PackReport,
    build_report,
    build_summary,
    render_json,
    render_markdown,
    render_summary_markdown,
)
from docgate.reporting.writer import write_run
from docgate.rules.engine import evaluate
from docgate.rules.titles import rule_titles
from docgate.workflow.graph import build_graph, run_pack
from docgate.workflow.runner import report_of
from tests.factories import absent, baseline_extraction, ok, pr_line
from tests.graph_support import pack_path, replay_deps


@pytest.fixture(scope="module")
def reports() -> dict[int, PackReport]:
    graph = build_graph(replay_deps())
    out: dict[int, PackReport] = {}
    for n in range(1, 11):
        state = run_pack(graph, f"supplier-pack-{n:02d}", pack_path(n))
        out[n] = report_of(state)
    return out


# ---- explain: pure, from structured findings --------------------------------------------


def _verdict(**overrides: Any) -> Any:
    return evaluate(baseline_extraction(**overrides), pr_line())


def test_explain_approve() -> None:
    assert explain(_verdict(), [], DEFAULT_CONFIG) == "All 12 checks passed."


def test_explain_reject_puts_primary_rule_first_and_lists_the_rest() -> None:
    verdict = _verdict(
        advance_pct=ok(Decimal("40"), "40% advance"),
        delivery_days=ok(60, "within 60 days"),
    )
    text = explain(verdict, [], DEFAULT_CONFIG)
    assert text.startswith("Rejected")
    assert text.index("R2") < text.index("Also rejected by") < text.rindex("R5")
    assert "40% advance" in text


def test_explain_reject_lists_review_flags_after_rejections() -> None:
    verdict = _verdict(
        advance_pct=ok(Decimal("40"), "40% advance"),
        validity_days=ok(10, "valid for 10 days"),
    )
    text = explain(verdict, [], DEFAULT_CONFIG)
    assert text.index("R2") < text.index("Also flagged") < text.index("H7")


def test_explain_needs_person_lists_each_finding_with_evidence() -> None:
    verdict = _verdict(payment_days=ok(DayRange(min=30, max=90), "30 to 90 days"))
    text = explain(verdict, [], DEFAULT_CONFIG)
    assert text.startswith("A person must check")
    assert "H3" in text and "30 to 90 days" in text


def test_explain_lists_unknowns_as_could_not_be_checked() -> None:
    verdict = _verdict(unit_price=absent())
    text = explain(verdict, [], DEFAULT_CONFIG)
    assert "Could not be checked" in text and "R1" in text


def test_explain_failed_fail_without_quote_says_not_found() -> None:
    verdict = _verdict(tin=absent(), bin=absent())
    text = explain(verdict, [], DEFAULT_CONFIG)
    assert text.startswith("Rejected") and "not found in the document" in text


# ---- per-pack report content -------------------------------------------------------------


def test_pack_03_reject_report(reports: dict[int, PackReport]) -> None:
    r = reports[3]
    assert r.decision is Decision.REJECT and not r.needs_human
    assert r.primary_rule == "R1"
    assert r.price_delta_pct == Decimal("9.05")
    r1 = next(x for x in r.rule_results if x.rule_id == "R1")
    assert r1.status == "FAIL" and r1.evidence_quote
    assert len(r.rule_results) == 12


def test_pack_09_lists_both_findings_with_quotes_and_the_arithmetic(
    reports: dict[int, PackReport],
) -> None:
    r = reports[9]
    assert r.decision is Decision.NEEDS_PERSON and r.needs_human
    failing = {x.rule_id: x.evidence_quote for x in r.rule_results if x.status == "FAIL"}
    assert set(failing) == {"H3", "H6"}
    assert "30 to 90 days" in (failing["H3"] or "")
    line = next(a for a in r.arithmetic if a.check == "line_total")
    assert (line.expected, line.actual, line.ok) == (
        Decimal("320000.00"),
        Decimal("322000.00"),
        False,
    )


def test_pack_08_missing_ids_are_reported_as_not_found(reports: dict[int, PackReport]) -> None:
    r = reports[8]
    assert r.primary_rule == "R4"
    assert "not found in the document" in r.explanation
    tin = next(f for f in r.fields if f.name == "tin")
    assert tin.status == "MISSING" and tin.value is None


def test_pack_10_reject_primary_r5_with_h5_and_unknowns(reports: dict[int, PackReport]) -> None:
    r = reports[10]
    assert r.primary_rule == "R5"
    assert r.price_delta_pct is None and r.price_note
    text = r.explanation
    assert text.index("R5") < text.index("Also flagged") < text.index("H5")
    assert "Could not be checked" in text and "R1" in text


def test_report_deltas_agree_with_rule_messages(reports: dict[int, PackReport]) -> None:
    h1 = next(x for x in reports[4].rule_results if x.rule_id == "H1")
    assert reports[4].price_delta_pct == Decimal("2.31") and "+2.31%" in h1.message
    h2 = next(x for x in reports[7].rule_results if x.rule_id == "H2")
    assert reports[7].qty_delta_pct == Decimal("-17.50") and "-17.50%" in h2.message


def test_every_ok_field_has_value_and_quote(reports: dict[int, PackReport]) -> None:
    for r in reports.values():
        for f in r.fields:
            if f.status == "OK":
                assert f.value is not None and f.quote


def test_report_titles_cover_all_rules() -> None:
    titles = rule_titles(DEFAULT_CONFIG)
    assert set(titles) == {f"R{i}" for i in range(1, 6)} | {f"H{i}" for i in range(1, 8)}
    assert "3%" in titles["R1"] and "45" in titles["R5"]


# ---- rendering and writing ---------------------------------------------------------------


def test_json_round_trips_with_decimals_as_strings(reports: dict[int, PackReport]) -> None:
    data = json.loads(render_json(reports[3]))
    assert data["price_delta_pct"] == "9.05"
    assert data["decision"] == "Reject"
    assert data["human_decision"] is None
    assert PackReport.model_validate(data) == reports[3]


def test_markdown_has_reason_quotes_and_rule_table(reports: dict[int, PackReport]) -> None:
    md = render_markdown(reports[9])
    assert "Needs a person to check" in md
    assert "| H6 |" in md and "Subtotal 322,000.00" in md
    assert "320000.00" in md and "322000.00" in md


def test_summary_counts_and_rows(reports: dict[int, PackReport]) -> None:
    summary = build_summary(list(reports.values()))
    assert len(summary.rows) == 10
    assert summary.counts == {"Approve": 2, "Reject": 5, "Needs a person to check": 3}
    md = render_summary_markdown(summary)
    assert "supplier-pack-09" in md and "Needs a person to check" in md


def test_write_run_is_deterministic(tmp_path: Path, reports: dict[int, PackReport]) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    write_run(list(reports.values()), first)
    write_run(list(reports.values()), second)
    names = sorted(p.name for p in first.iterdir())
    assert names == sorted(p.name for p in second.iterdir())
    assert "supplier-pack-04.json" in names and "summary.md" in names and "summary.json" in names
    for name in names:
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_escalated_pack_report_shows_the_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    state = run_pack(build_graph(replay_deps()), "bad", bad)
    r = report_of(state)
    assert r.decision is Decision.NEEDS_PERSON and r.needs_human
    assert r.errors and r.errors[0].node == "ingest"
    assert r.fields == [] and r.rule_results == []
    assert "a person must check" in r.explanation.lower()
    assert "ingest" in render_markdown(r)


def test_build_report_is_pure_over_state() -> None:
    state = run_pack(build_graph(replay_deps()), "supplier-pack-04", pack_path(4))
    again = build_report(
        pack_id=state["pack_id"],
        source_file="supplier-pack-04.pdf",
        verdict=state["verdict"],
        extraction=state["extraction"],
        issues=state["issues"],
        comparison=state["comparison"],
        errors=state["errors"],
        cfg=DEFAULT_CONFIG,
    )
    assert again == report_of(state)
