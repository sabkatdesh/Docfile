"""Cross-platform task runner (Windows has no `make`). `Makefile` is a thin wrapper."""

from __future__ import annotations

import os
import shutil
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


WEB = ROOT / "web"
WEB_CACHE = WEB / ".npm-cache"  # keeps npm's download cache on the project's drive, not C:


def web_env(env: Mapping[str, str]) -> dict[str, str]:
    """The environment for npm: cache inside web/ unless the caller chose one."""
    return {"npm_config_cache": str(WEB_CACHE), **env}


def web_dist_notice(root: Path) -> str | None:
    """What to tell someone who serves the API before the front end is built; None when built."""
    if (root / "web" / "dist" / "index.html").is_file():
        return None
    return (
        "note: the web front end is not built (web/dist is missing), so the browser will show "
        "only a placeholder page. The API itself works.\n"
        "      Build it once with:  python tasks.py web-install  then  python tasks.py web-build"
    )


def npm(*args: str) -> int:
    exe = shutil.which("npm")
    if exe is None:
        print("npm was not found. Install Node.js 20+ to build the front end.", file=sys.stderr)
        return 127
    print("+ npm", " ".join(args), flush=True)
    return subprocess.call([exe, *args], cwd=WEB, env=web_env(os.environ))


def web_install(_args: list[str]) -> int:
    return npm("install", "--no-audit", "--no-fund")


def web_dev(args: list[str]) -> int:
    return npm("run", "dev", "--", *args)


def web_build(_args: list[str]) -> int:
    return npm("run", "build")


def web_test(args: list[str]) -> int:
    return npm("run", "test", "--", *args)


def web_check(_args: list[str]) -> int:
    steps = ["lint", "typecheck", "check:types-drift", "test"]
    codes = [npm("run", step) for step in steps]
    return 0 if not any(codes) else 1


def serve(args: list[str]) -> int:
    notice = web_dist_notice(ROOT)
    if notice:
        print(notice, file=sys.stderr, flush=True)
    return _cli("serve")(args)


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
    "serve": serve,
    "web-install": web_install,
    "web-dev": web_dev,
    "web-build": web_build,
    "web-test": web_test,
    "web-check": web_check,
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
