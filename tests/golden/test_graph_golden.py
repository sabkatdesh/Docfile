"""M3 done-when: the real graph, in replay, reproduces the golden set with no unsafe error."""

from __future__ import annotations

import socket

import pytest

from docgate.domain.models import Decision, RuleStatus
from docgate.rules.engine import EXPECTED_IDS
from docgate.workflow.graph import build_graph, run_pack
from tests.golden.expected import EXPECTED_NON_PASS, GOLDEN
from tests.graph_support import pack_path, replay_deps


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("replay must never touch the network")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)


@pytest.mark.parametrize("n", sorted(GOLDEN))
def test_graph_decision_matches_golden(n: int) -> None:
    state = run_pack(build_graph(replay_deps()), f"supplier-pack-{n:02d}", pack_path(n))
    assert state["errors"] == []
    assert state["verdict"].decision is GOLDEN[n], state["verdict"].reason


@pytest.mark.parametrize("n", sorted(GOLDEN))
def test_graph_rule_vector_matches_golden(n: int) -> None:
    state = run_pack(build_graph(replay_deps()), f"supplier-pack-{n:02d}", pack_path(n))
    got = {r.rule_id: r.status for r in state["verdict"].rule_results}
    want = {i: EXPECTED_NON_PASS[n].get(i, RuleStatus.PASS) for i in EXPECTED_IDS}
    assert got == want


def test_no_unsafe_errors_and_totals() -> None:
    graph = build_graph(replay_deps())
    decisions = {
        n: run_pack(graph, f"supplier-pack-{n:02d}", pack_path(n))["verdict"].decision
        for n in GOLDEN
    }
    unsafe = [n for n, d in decisions.items() if d is Decision.APPROVE and GOLDEN[n] is not d]
    assert unsafe == []
    assert decisions == GOLDEN


@pytest.mark.parametrize("n", [4, 7, 9])
def test_needs_person_packs_end_cleanly_and_flag_a_human(n: int) -> None:
    state = run_pack(build_graph(replay_deps()), f"supplier-pack-{n:02d}", pack_path(n))
    verdict = state["verdict"]
    assert verdict.needs_human
    assert verdict.human_decision is None  # M4 fills this in after the pause


@pytest.mark.parametrize("n", [1, 2, 3, 5, 6, 8, 10])
def test_other_packs_do_not_flag_a_human(n: int) -> None:
    state = run_pack(build_graph(replay_deps()), f"supplier-pack-{n:02d}", pack_path(n))
    assert not state["verdict"].needs_human
