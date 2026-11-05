"""tasks.py picks the project's .venv interpreter when launched from another Python."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import tasks


def _make_venv(root: Path) -> Path:
    exe = root / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
    exe.mkdir(parents=True)
    python = exe / ("python.exe" if sys.platform == "win32" else "python")
    python.write_bytes(b"")
    return python


def test_picks_the_venv_python_when_launched_from_another_python(tmp_path: Path) -> None:
    python = _make_venv(tmp_path)
    assert tasks.pick_interpreter(tmp_path, str(tmp_path / "elsewhere"), {}) == python


def test_none_when_already_running_inside_the_venv(tmp_path: Path) -> None:
    _make_venv(tmp_path)
    assert tasks.pick_interpreter(tmp_path, str(tmp_path / ".venv"), {}) is None


def test_none_when_the_guard_variable_is_set(tmp_path: Path) -> None:
    _make_venv(tmp_path)
    assert tasks.pick_interpreter(tmp_path, "x", {"DOCGATE_NO_REEXEC": "1"}) is None


def test_none_when_there_is_no_venv(tmp_path: Path) -> None:
    assert tasks.pick_interpreter(tmp_path, "x", {}) is None


@pytest.mark.parametrize("command", ["setup"])
def test_setup_never_re_execs(command: str) -> None:
    assert not tasks.wants_venv(command)


@pytest.mark.parametrize("command", ["check", "demo", "eval", "run"])
def test_other_commands_may_re_exec(command: str) -> None:
    assert tasks.wants_venv(command)
