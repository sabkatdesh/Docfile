"""Cross-platform task runner (Windows has no `make`). `Makefile` is a thin wrapper."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable

PY = sys.executable


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


def _not_yet(name: str, milestone: str) -> Callable[[list[str]], int]:
    def stub(_args: list[str]) -> int:
        print(f"`{name}` is not available until {milestone}.", file=sys.stderr)
        return 1

    return stub


COMMANDS: dict[str, Callable[[list[str]], int]] = {
    "setup": setup,
    "check": check,
    "demo": _not_yet("demo", "M5.5/M5"),
    "live": _not_yet("live", "M3"),
    "extract": _cli("extract"),
    "record": _cli("record"),
    "eval": _not_yet("eval", "M3"),
}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(f"usage: python tasks.py {{{'|'.join(COMMANDS)}}}", file=sys.stderr)
        return 2
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
