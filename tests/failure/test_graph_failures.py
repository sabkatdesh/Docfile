"""M5 failure suite, graph level. Whatever goes wrong, the real graph ends in "Needs a person"
with a reason and never in Approve. No network and no real sleeping."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from docgate.domain.models import Decision, FieldStatus, RuleStatus
from docgate.extraction.factory import LLMStack, build_llm_stack
from docgate.extraction.llm import LLMExtractor
from docgate.extraction.prompt import load_prompt
from docgate.llm.provider import (
    LLMRateLimitedError,
    LLMTimeoutError,
)
from docgate.llm.retry import RetryingProvider, RetryPolicy
from docgate.settings import Settings, load_settings, request_params
from docgate.workflow.graph import Deps, build_graph, run_pack
from docgate.workflow.state import PackState
from tests.fakes import FakeClock, FakeProvider
from tests.graph_support import PR_LINES, RECORDED, pack_path, replay_deps
from tests.unit.test_pdf import BLANK_PDF
from tests.unit.test_workflow import Raising

BASE = 1  # an Approve pack: the strongest place to show a failure never approves


def _run(deps: Deps, path: Path | None = None) -> PackState:
    return run_pack(build_graph(deps), "supplier-pack-01", path or pack_path(BASE))


def _needs_person(state: PackState) -> None:
    assert state["verdict"].decision is Decision.NEEDS_PERSON
    assert state["verdict"].needs_human


def _extractor(provider: object) -> LLMExtractor:
    return LLMExtractor(provider, load_prompt(), request_params(Settings()))  # type: ignore[arg-type]


# -- input files ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "content", "reason_has"),
    [
        ("zero.pdf", b"", "zero.pdf"),
        ("image.pdf", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "image.pdf"),
        ("blank.pdf", BLANK_PDF, "no extractable text"),
    ],
)
def test_bad_input_file_escalates_at_ingest(
    tmp_path: Path, name: str, content: bytes, reason_has: str
) -> None:
    bad = tmp_path / name
    bad.write_bytes(content)
    state = _run(replay_deps(), bad)
    _needs_person(state)
    assert [e.node for e in state["errors"]] == ["ingest"]
    assert reason_has in state["verdict"].reason


def test_missing_pdf_escalates_at_ingest(tmp_path: Path) -> None:
    state = _run(replay_deps(), tmp_path / "gone.pdf")
    _needs_person(state)
    assert "gone.pdf" in state["verdict"].reason


# -- purchase request ----------------------------------------------------------------------


def test_pr_without_the_quoted_item_needs_a_person() -> None:
    lines = {k: v for k, v in PR_LINES.items() if k != "A"}
    state = _run(replay_deps(pr_lines=lines))
    _needs_person(state)
    got = {r.rule_id: r.status for r in state["verdict"].rule_results}
    assert got["R1"] is got["H1"] is got["H2"] is RuleStatus.UNKNOWN
    assert state["errors"] == []


# -- recordings ----------------------------------------------------------------------------


def _recorded_copy(tmp_path: Path) -> tuple[Path, Path]:
    copy = tmp_path / "recorded"
    shutil.copytree(RECORDED, copy)
    return copy, next(copy.glob("supplier-pack-01__*.json"))


@pytest.mark.parametrize(
    "damage",
    ["{broken", "[]", '"just a string"', "", '{"key": "KEY"}', '{"key": "KEY", "response": 7}'],
)
def test_corrupt_recording_escalates_with_a_clear_reason(tmp_path: Path, damage: str) -> None:
    copy, victim = _recorded_copy(tmp_path)
    key = json.loads(victim.read_text("utf-8"))["key"]
    victim.write_text(damage.replace("KEY", key), encoding="utf-8")
    deps = replay_deps(llm=_stack(copy).extractor)
    state = _run(deps)
    _needs_person(state)
    assert state["extraction"].unit_price.status is FieldStatus.UNVERIFIED
    assert any("corrupt" in i.reason for i in state["issues"])


def _stack(recorded: Path) -> LLMStack:
    return build_llm_stack(load_settings({"DOCGATE_RECORDED_DIR": str(recorded)}))


# -- the model service ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "error", [LLMRateLimitedError("429 too many requests"), LLMTimeoutError("timed out")]
)
def test_llm_that_keeps_failing_escalates_after_retries(error: Exception) -> None:
    clock = FakeClock()
    fake = FakeProvider([error] * 4)
    provider = RetryingProvider(fake, clock, RetryPolicy())
    state = _run(replay_deps(llm=_extractor(provider)))
    _needs_person(state)
    assert fake.calls == 4  # the policy's attempts, then it gives up
    assert len(clock.sleeps) == 3  # fake time only: the test never really waits
    assert any("gave up after 4 attempts" in i.reason for i in state["issues"])


def test_a_very_long_retry_after_escalates_instead_of_hanging() -> None:
    clock = FakeClock()
    provider = RetryingProvider(
        FakeProvider([LLMRateLimitedError("daily cap", retry_after=3600.0)]), clock, RetryPolicy()
    )
    state = _run(replay_deps(llm=_extractor(provider)))
    _needs_person(state)
    assert clock.sleeps == []
    assert any("too long" in i.reason for i in state["issues"])


def test_malformed_json_twice_escalates() -> None:
    fake = FakeProvider(["not json", "{still not"])
    state = _run(replay_deps(llm=_extractor(fake)))
    _needs_person(state)
    assert fake.calls == 2  # retried once, as the spec says, then escalated


@pytest.mark.parametrize("which", ["llm", "regex"])
def test_an_extractor_that_raises_escalates(which: str) -> None:
    boom = Raising(which, RuntimeError("boom"))
    state = _run(replay_deps(llm=boom) if which == "llm" else replay_deps(regex=boom))
    _needs_person(state)
    assert state["errors"][0].node == f"extract_{which}"
