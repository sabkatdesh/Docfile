"""Batch runner and the thin CLI. Eval is checked end to end, including when it must fail."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from docgate.cli import main
from docgate.domain.models import Decision
from docgate.llm.provider import LLMConfigError
from docgate.workflow.graph import build_graph
from docgate.workflow.runner import OperatorError, pack_number, run_packs
from tests.graph_support import pack_path, replay_deps
from tests.unit.test_workflow import Raising


@pytest.fixture(autouse=True)
def repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(Path(__file__).parents[2])
    monkeypatch.delenv("DOCGATE_PROVIDER", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    # Never read the developer's .env here: a real key would make these tests go live.
    monkeypatch.setattr("docgate.cli._environment", lambda: dict(os.environ))


def test_pack_number() -> None:
    assert pack_number("supplier-pack-04") == 4
    with pytest.raises(ValueError, match="pack number"):
        pack_number("bad")


def test_run_packs_returns_one_state_per_pack() -> None:
    graph = build_graph(replay_deps())
    states = run_packs(graph, [pack_path(1), pack_path(3)])
    assert [s["pack_id"] for s in states] == ["supplier-pack-01", "supplier-pack-03"]
    assert [s["verdict"].decision for s in states] == [Decision.APPROVE, Decision.REJECT]


def test_config_error_stops_the_batch_instead_of_escalating_every_pack() -> None:
    graph = build_graph(replay_deps(llm=Raising("llm", LLMConfigError("bad key"))))
    with pytest.raises(OperatorError, match="bad key"):
        run_packs(graph, [pack_path(1), pack_path(2)])


def test_ordinary_failure_does_not_stop_the_batch() -> None:
    graph = build_graph(replay_deps(llm=Raising("llm", RuntimeError("boom"))))
    states = run_packs(graph, [pack_path(1), pack_path(2)])
    assert [s["verdict"].decision for s in states] == [Decision.NEEDS_PERSON] * 2


def test_eval_passes_10_of_10_and_writes_reports(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["eval", "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "accuracy: 10/10" in out and "unsafe errors: 0" in out
    assert "MISMATCH" not in out
    assert (tmp_path / "summary.md").is_file() and (tmp_path / "supplier-pack-09.md").is_file()
    data = json.loads((tmp_path / "eval.json").read_text("utf-8"))
    assert data["correct"] == 10 and data["unsafe"] == []


def _golden_with(tmp_path: Path, **changes: str) -> Path:
    real = json.loads(Path("data/golden/expected.json").read_text("utf-8"))
    for pack, verdict in changes.items():
        real["expected"][pack.removeprefix("p")] = verdict
    path = tmp_path / "golden.json"
    path.write_text(json.dumps(real), encoding="utf-8")
    return path


def test_eval_fails_on_a_mismatch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    golden = _golden_with(tmp_path, p4="Reject")  # system says Needs a person
    code = main(["eval", "--out", str(tmp_path / "o"), "--golden", str(golden)])
    out = capsys.readouterr().out
    assert code == 1
    assert "accuracy: 9/10" in out and "MISMATCH" in out
    assert "unsafe errors: 0" in out


def test_eval_flags_a_wrong_approve_as_unsafe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    golden = _golden_with(tmp_path, p1="Reject")  # system Approves pack 01
    code = main(["eval", "--out", str(tmp_path / "o"), "--golden", str(golden)])
    out = capsys.readouterr().out
    assert code == 1
    assert "unsafe errors: 1 (packs 1)" in out


def test_eval_ignores_a_groq_provider_in_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DOCGATE_PROVIDER", "groq")  # must not go live: eval is replay-only
    assert main(["eval", "--out", str(tmp_path)]) == 0
    assert "10/10" in capsys.readouterr().out


def test_run_single_pack_writes_its_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(["run", "--pack", "9", "--out", str(tmp_path), "--db", str(tmp_path / "ck.sqlite")])
        == 0
    )
    assert "Needs a person to check" in capsys.readouterr().out
    assert (tmp_path / "supplier-pack-09.json").is_file()
    assert not (tmp_path / "supplier-pack-01.json").exists()


def test_live_run_without_a_key_stops_with_a_clear_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "run",
            "--provider",
            "groq",
            "--pack",
            "1",
            "--out",
            str(tmp_path),
            "--db",
            str(tmp_path / "ck.sqlite"),
        ]
    )
    assert code == 2
    assert "GROQ_API_KEY" in capsys.readouterr().err


def test_bad_golden_file_is_a_clear_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "g.json"
    bad.write_text("nope", encoding="utf-8")
    assert main(["eval", "--out", str(tmp_path / "o"), "--golden", str(bad)]) == 2
    assert "golden" in capsys.readouterr().err
