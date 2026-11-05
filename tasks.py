"""Cross-platform task runner (Windows has no `make`). `Makefile` is a thin wrapper."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

PY = sys.executable
ROOT = Path(__file__).resolve().parent
NO_REEXEC = "DOCGATE_NO_REEXEC"  # set to stop the hand-off (and to prevent a loop)


def pick_interpreter(root: Path, current_prefix: str, env: Mapping[str, str]) -> Path | None:
    """The project's .venv python, if we were started from some other Python."""
    if env.get(NO_REEXEC):
        return None
    venv = root / ".venv"
    python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.is_file():
        return None
    return None if Path(current_prefix).resolve() == venv.resolve() else python


def wants_venv(command: str) -> bool:
    return command != "setup"  # setup installs into whichever Python the user chose


def run(*args: str) -> int:
    print("+", " ".join(args), flush=True)
    return subprocess.call(args)


def setup(_args: list[str]) -> int:
    return run(PY, "-m", "pip", "install", "-e", ".[dev]")


def check(_args: list[str]) -> int:
    steps = [
        (PY, "-m", "ruff", "check", "."),
        (PY, "-m", "ruff", "format", "--check", "."),
        (PY, "-m", "mypy"),
        (PY, "-m", "pytest"),
    ]
    # Run every step so one report shows all failures, but fail if any failed.
    codes = [run(*step) for step in steps]
    return 0 if not any(codes) else 1


def _cli(command: str) -> Callable[[list[str]], int]:
    """Forward to the thin CLI, e.g. `python tasks.py record --smoke`."""

    def forward(args: list[str]) -> int:
        return run(PY, "-m", "docgate.cli", command, *args)

    return forward


COMMANDS: dict[str, Callable[[list[str]], int]] = {
    "setup": setup,
    "check": check,
    "demo": _cli("demo"),
    "run": _cli("run"),
    "live": lambda args: _cli("run")(["--provider", "groq", *args]),
    "extract": _cli("extract"),
    "record": _cli("record"),
    "eval": _cli("eval"),
    "review": _cli("review"),
    "serve": _cli("serve"),
    "openapi": _cli("openapi"),
    "mutation-report": lambda args: run(PY, "-m", "scripts.mutation_report", *args),
}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(f"usage: python tasks.py {{{'|'.join(COMMANDS)}}}", file=sys.stderr)
        return 2
    command = argv[1]
    venv_python = pick_interpreter(ROOT, sys.prefix, os.environ) if wants_venv(command) else None
    if venv_python is not None:
        print(f"using {venv_python}", file=sys.stderr)
        env = {**os.environ, NO_REEXEC: "1"}
        return subprocess.call([str(venv_python), *argv], env=env)
    return COMMANDS[command](argv[2:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
