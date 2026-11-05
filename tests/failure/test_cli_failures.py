"""M5 failure suite, command line. Expected failures print one readable line and exit non-zero:
never a stack trace, never an approval."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from docgate.cli import main

ROOT = Path(__file__).parents[2]


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCGATE_PROVIDER", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr("docgate.cli._environment", lambda: dict(os.environ))


@pytest.fixture
def work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A private copy of the data, so a test can break it and run from there."""
    shutil.copytree(ROOT / "data", tmp_path / "data")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _fails_cleanly(
    capsys: pytest.CaptureFixture[str], code: int, expect_code: int, *words: str
) -> None:
    captured = capsys.readouterr()
    assert code == expect_code
    assert "Traceback" not in captured.err and "Traceback" not in captured.out
    for word in words:
        assert word in captured.err
    assert "Approve" not in captured.out.replace("Approve  ", "")  # nothing approved on failure


# -- live mode without a key -------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["run", "--provider", "groq", "--pack", "1"],
        ["run", "--provider", "groq"],
        ["record", "--smoke"],
        ["record"],
    ],
)
def test_live_mode_without_a_key_is_a_clear_message(
    work: Path, capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    code = main([*argv, *(["--db", "ck.sqlite"] if argv[0] == "run" else [])])
    _fails_cleanly(capsys, code, 2, "GROQ_API_KEY")
    assert not (work / "ck.sqlite").exists()  # a config error must not leave a database behind


def test_extract_with_groq_in_the_environment_but_no_key(
    work: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DOCGATE_PROVIDER", "groq")
    _fails_cleanly(capsys, main(["extract"]), 2, "GROQ_API_KEY")


# -- missing or damaged inputs -----------------------------------------------------------------


@pytest.mark.parametrize("command", ["eval", "run", "demo"])
def test_missing_sample_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    _fails_cleanly(capsys, main([command]), 2, "supplier packs")


def test_missing_purchase_request(work: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (work / "data" / "sample" / "purchase-request.csv").unlink()
    _fails_cleanly(capsys, main(["eval"]), 2, "purchase-request.csv")


@pytest.mark.parametrize(
    "content",
    [
        "",  # empty file
        "PR number,Item\nPR-1,A\n",  # columns missing
        "PR number,Item,Description,Unit,Quantity requested,Maximum unit price (BDT)\n"
        "PR-1,A,x,metre,lots,480.00\n",  # not a number
        "PR number,Item,Description,Unit,Quantity requested,Maximum unit price (BDT)\n"
        "PR-1,A,x,metre,1,1\nPR-1,A,x,metre,1,1\n",  # duplicate item
    ],
    ids=["empty", "missing-columns", "bad-number", "duplicate-item"],
)
def test_malformed_purchase_request(
    work: Path, capsys: pytest.CaptureFixture[str], content: str
) -> None:
    (work / "data" / "sample" / "purchase-request.csv").write_text(content, encoding="utf-8")
    code = main(["eval"])
    # An empty table is valid CSV with no lines: every pack then needs a person, so eval fails
    # on its golden comparison (exit 1) rather than approving anything.
    assert code in (1, 2)
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    if code == 2:
        assert "purchase-request.csv" in captured.err
    assert "unsafe errors: 0" in captured.out or code == 2


def test_missing_golden_file(work: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _fails_cleanly(capsys, main(["eval", "--golden", "nope.json"]), 2, "golden")


def test_a_removed_pack_file_is_a_mismatch_not_a_pass(
    work: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (work / "data" / "sample" / "supplier-pack-05.pdf").unlink()
    code = main(["eval", "--out", "out"])
    out = capsys.readouterr().out
    assert code == 1
    assert "MISMATCH" in out and "unsafe errors: 0" in out


@pytest.mark.parametrize("flags", [["--pack", "99"], ["--pack", "1", "--pack", "99"]])
def test_a_pack_number_with_no_file_is_an_error(
    work: Path, capsys: pytest.CaptureFixture[str], flags: list[str]
) -> None:
    code = main(["run", *flags, "--db", "ck.sqlite", "--out", "out"])
    _fails_cleanly(capsys, code, 2, "99")
    assert not (work / "ck.sqlite").exists()
