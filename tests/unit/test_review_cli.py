"""The review commands end to end. Each `main()` call opens its own connection, so every command
after the first `run` is effectively a new process."""

from __future__ import annotations

import getpass
import json
import os
from pathlib import Path

import pytest

from docgate.cli import main


@pytest.fixture(autouse=True)
def repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(Path(__file__).parents[2])
    monkeypatch.delenv("DOCGATE_PROVIDER", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr("docgate.cli._environment", lambda: dict(os.environ))


@pytest.fixture
def paths(tmp_path: Path) -> list[str]:
    return ["--db", str(tmp_path / "ck.sqlite")]


@pytest.fixture
def out(tmp_path: Path) -> Path:
    return tmp_path / "out"


def _run(paths: list[str], out: Path, *extra: str) -> int:
    return main(["run", *paths, "--out", str(out), *extra])


def _resolve(
    paths: list[str], out: Path, pack: str, *, reason: str, decision: str = "reject", **kw: str
) -> int:
    args = ["review", "resolve", pack, "--decision", decision, "--reason", reason]
    for flag, value in kw.items():
        args += [f"--{flag}", value]
    return main([*args, *paths, "--out", str(out)])


def test_run_reports_paused_packs(
    paths: list[str], out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(paths, out) == 0
    lines = capsys.readouterr().out.splitlines()
    paused = sorted(ln.split()[0] for ln in lines if "awaiting review" in ln)
    assert paused == ["supplier-pack-04", "supplier-pack-07", "supplier-pack-09"]


def test_list_shows_exactly_the_paused_packs(
    paths: list[str], out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run(paths, out)
    capsys.readouterr()
    assert main(["review", "list", *paths]) == 0
    shown = capsys.readouterr().out
    for n in ("04", "07", "09"):
        assert f"supplier-pack-{n}" in shown
    assert "supplier-pack-01" not in shown and "supplier-pack-03" not in shown


def test_show_prints_rules_and_evidence(
    paths: list[str], out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run(paths, out)
    capsys.readouterr()
    assert main(["review", "show", "supplier-pack-09", *paths]) == 0
    shown = capsys.readouterr().out
    assert "H3" in shown and "H6" in shown and "322,000" in shown
    assert "pending" in shown


def test_resolve_writes_both_decisions_to_the_report(
    paths: list[str], out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run(paths, out)
    code = _resolve(paths, out, "supplier-pack-09", reason="Arithmetic error", reviewer="sabkat")
    assert code == 0
    md = (out / "supplier-pack-09.md").read_text("utf-8")
    assert "# supplier-pack-09: Needs a person to check" in md
    assert "Human decision: Reject" in md and "Arithmetic error" in md and "sabkat" in md
    data = json.loads((out / "supplier-pack-09.json").read_text("utf-8"))
    assert data["decision"] == "Needs a person to check"
    assert data["human_review"]["decision"] == "Reject"
    assert "Reject" in (out / "summary.md").read_text("utf-8")
    capsys.readouterr()
    main(["review", "list", *paths])
    assert "supplier-pack-09" not in capsys.readouterr().out


def test_reviewer_defaults_to_the_os_username(
    paths: list[str], out: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(getpass, "getuser", lambda: "osuser")
    _run(paths, out)
    assert _resolve(paths, out, "supplier-pack-04", reason="ok", decision="approve") == 0
    data = json.loads((out / "supplier-pack-04.json").read_text("utf-8"))
    assert data["human_review"]["reviewer"] == "osuser"


def test_double_resolve_is_an_error_and_keeps_the_first(
    paths: list[str], out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run(paths, out)
    _resolve(paths, out, "supplier-pack-04", reason="first", decision="approve", reviewer="alice")
    capsys.readouterr()
    code = _resolve(paths, out, "supplier-pack-04", reason="second", reviewer="bob")
    assert code == 2
    assert "already resolved by alice" in capsys.readouterr().err
    data = json.loads((out / "supplier-pack-04.json").read_text("utf-8"))
    assert data["human_review"]["reason"] == "first"


@pytest.mark.parametrize("reason", ["", "   "])
def test_empty_reason_is_an_error(
    paths: list[str], out: Path, capsys: pytest.CaptureFixture[str], reason: str
) -> None:
    _run(paths, out)
    capsys.readouterr()
    assert _resolve(paths, out, "supplier-pack-07", reason=reason) == 2
    assert "reason" in capsys.readouterr().err
    main(["review", "list", *paths])
    assert "supplier-pack-07" in capsys.readouterr().out  # still pending


def test_unknown_pack_is_an_error(
    paths: list[str], out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run(paths, out)
    capsys.readouterr()
    assert _resolve(paths, out, "supplier-pack-99", reason="x") == 2
    assert "unknown pack" in capsys.readouterr().err


def test_a_machine_final_pack_cannot_be_resolved(
    paths: list[str], out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run(paths, out)
    capsys.readouterr()
    assert _resolve(paths, out, "supplier-pack-01", reason="override", decision="reject") == 2
    assert "final" in capsys.readouterr().err


def test_missing_database_is_a_clear_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["review", "list", "--db", str(tmp_path / "nope.sqlite")])
    assert code == 2
    assert "run" in capsys.readouterr().err
    assert not (tmp_path / "nope.sqlite").exists()  # a lookup must not create the file


def test_rerun_does_not_restart_a_pack_on_record(
    paths: list[str], out: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run(paths, out)
    _resolve(paths, out, "supplier-pack-04", reason="kept", decision="approve", reviewer="alice")
    capsys.readouterr()
    assert _run(paths, out, "--resume") == 0  # a fresh start is the default; resuming is explicit
    assert "already on record" in capsys.readouterr().out
    data = json.loads((out / "supplier-pack-04.json").read_text("utf-8"))
    assert data["human_review"]["reason"] == "kept"
