"""`run` starts from a fresh checkpoint database unless asked to resume, and never discards
reviews that still wait for a person."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from docgate.cli import main
from docgate.review.fresh import start_fresh
from docgate.review.store import ReviewError


@pytest.fixture(autouse=True)
def repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(Path(__file__).parents[2])
    monkeypatch.delenv("DOCGATE_PROVIDER", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr("docgate.cli._environment", lambda: dict(os.environ))


def _run(tmp_path: Path, out: str, *extra: str) -> int:
    return main(["run", "--db", str(tmp_path / "ck.sqlite"), "--out", str(tmp_path / out), *extra])


def test_run_default_ignores_a_leftover_database(tmp_path: Path) -> None:
    assert _run(tmp_path, "first", "--pack", "1") == 0  # pack 01 approves: nothing pending
    assert _run(tmp_path, "second", "--pack", "3") == 0
    assert (tmp_path / "second" / "supplier-pack-03.json").is_file()
    assert not (tmp_path / "second" / "supplier-pack-01.json").exists()  # old record not reused


def test_run_refuses_to_discard_reviews_that_are_still_pending(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(tmp_path, "first", "--pack", "4") == 0
    before = (tmp_path / "ck.sqlite").read_bytes()
    capsys.readouterr()
    assert _run(tmp_path, "second") == 2
    err = capsys.readouterr().err
    assert "--resume" in err and "supplier-pack-04" in err
    assert (tmp_path / "ck.sqlite").read_bytes() == before  # nothing was deleted or changed
    assert not (tmp_path / "second").exists()


def test_resume_keeps_the_record(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(tmp_path, "first", "--pack", "4") == 0
    capsys.readouterr()
    assert _run(tmp_path, "second", "--pack", "4", "--resume") == 0
    assert "already on record" in capsys.readouterr().out


def test_an_unreadable_database_is_a_clear_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "ck.sqlite").write_bytes(b"this is not a database" * 50)
    assert _run(tmp_path, "out") == 2
    assert "ck.sqlite" in capsys.readouterr().err
    assert (tmp_path / "ck.sqlite").exists()  # not deleted: the operator decides


def test_start_fresh_removes_the_database_and_its_sidecar_files(tmp_path: Path) -> None:
    db = tmp_path / "ck.sqlite"
    sidecars = [db, Path(f"{db}-wal"), Path(f"{db}-shm")]
    for p in sidecars:
        p.write_bytes(b"x")
    start_fresh(db, lambda: [])
    assert not any(p.exists() for p in sidecars)


def test_start_fresh_is_a_no_op_without_a_database(tmp_path: Path) -> None:
    start_fresh(tmp_path / "none.sqlite", lambda: ["must not be called"])


def test_start_fresh_refuses_when_reviews_are_pending(tmp_path: Path) -> None:
    db = tmp_path / "ck.sqlite"
    db.write_bytes(b"x")
    with pytest.raises(ReviewError, match="--resume"):
        start_fresh(db, lambda: ["supplier-pack-07"])
    assert db.exists()
