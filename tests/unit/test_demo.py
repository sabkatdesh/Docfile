"""`demo`: all ten packs in replay mode on a fresh database; no key, no network."""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from docgate.cli import main

ROOT = Path(__file__).parents[2]
NETBLOCK = ROOT / "tests" / "support" / "netblock"


@pytest.fixture(autouse=True)
def repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    monkeypatch.delenv("DOCGATE_PROVIDER", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr("docgate.cli._environment", lambda: dict(os.environ))


def _demo(tmp_path: Path, *extra: str) -> int:
    return main(["demo", "--db", str(tmp_path / "d.sqlite"), "--out", str(tmp_path / "o"), *extra])


def _rows(out: str) -> dict[str, str]:
    return {
        m[1]: m[2].strip() for m in re.finditer(r"^(supplier-pack-\d+)\s+(\S.*?)\s{2,}", out, re.M)
    }


def test_demo_prints_ten_rows_and_the_pause_list(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _demo(tmp_path) == 0
    out = capsys.readouterr().out
    rows = _rows(out)
    assert len(rows) == 10
    values = list(rows.values())
    assert values.count("Approve") == 2
    assert values.count("Reject") == 5
    assert values.count("Needs a person to check") == 3
    assert "3 pack(s) waiting for a decision" in out
    for n in ("04", "07", "09"):
        assert f"supplier-pack-{n}" in out.split("waiting for a decision")[1]
    assert (tmp_path / "o" / "summary.md").is_file()


def test_demo_needs_no_key_and_no_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("demo must never touch the network")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    assert _demo(tmp_path) == 0
    assert len(_rows(capsys.readouterr().out)) == 10


def test_demo_ignores_a_groq_provider_and_key_in_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DOCGATE_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_not_a_real_key")
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: 1 / 0)
    assert _demo(tmp_path) == 0  # a live call would have hit the blocked socket
    assert len(_rows(capsys.readouterr().out)) == 10


def test_demo_ignores_a_leftover_database(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _demo(tmp_path) == 0
    clean = capsys.readouterr().out
    assert (
        main(
            [
                "review",
                "resolve",
                "supplier-pack-09",
                "--decision",
                "approve",
                "--reason",
                "left over",
                "--db",
                str(tmp_path / "d.sqlite"),
                "--out",
                str(tmp_path / "x"),
            ]
        )
        == 0
    )  # the old database now holds a decision
    capsys.readouterr()
    assert _demo(tmp_path) == 0
    again = capsys.readouterr().out
    assert _rows(again) == _rows(clean)
    assert "already on record" not in again
    assert "3 pack(s) waiting for a decision" in again  # 09 pending again, not resolved


def test_demo_replaces_a_junk_database_file(tmp_path: Path) -> None:
    (tmp_path / "d.sqlite").write_bytes(b"junk" * 100)
    assert _demo(tmp_path) == 0


def test_demo_without_the_data_directory_is_a_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["demo", "--db", "d.sqlite", "--out", "o"]) == 2
    err = capsys.readouterr().err
    assert "supplier packs" in err and "Traceback" not in err


def test_demo_runs_as_a_real_process_with_sockets_blocked(tmp_path: Path) -> None:
    work = tmp_path / "w"
    shutil.copytree(ROOT / "data", work / "data")
    env = {k: v for k, v in os.environ.items() if k not in {"GROQ_API_KEY", "DOCGATE_PROVIDER"}}
    env["PYTHONPATH"] = os.pathsep.join([str(NETBLOCK), str(ROOT / "src")])
    done = subprocess.run(
        [sys.executable, "-m", "docgate.cli", "demo"],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert len(_rows(done.stdout)) == 10
    assert "Traceback" not in done.stderr
