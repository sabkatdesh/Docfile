"""Prove the project works from nothing: copy or clone it, build a venv, install, demo, check.

    python scripts/fresh_clone.py --worktree   # the files as they would be committed (pre-commit)
    python scripts/fresh_clone.py              # a real `git clone` of HEAD (post-commit)

Slow (it installs every dependency) and needs network for pip only, so it is not part of `check`.
The demo stage runs with the API key removed and sockets blocked, as a reviewer without a key
would see it. Standard library only, so it runs before anything is installed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NETBLOCK = Path("tests") / "support" / "netblock"
EXPECTED_SUMMARY = "10 packs: 2 Approve, 3 Needs a person to check, 5 Reject"


def _git(*args: str, cwd: Path) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True, encoding="utf-8"
    )
    return done.stdout


def copy_worktree(dest: Path) -> None:
    """Tracked plus untracked-but-not-ignored files: what `git add -A` would commit."""
    names = _git("ls-files", "--cached", "--others", "--exclude-standard", cwd=ROOT).splitlines()
    for name in names:
        source = ROOT / name
        if source.is_file():  # a deleted-but-listed file has nothing to copy
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def clone_head(dest: Path) -> None:
    subprocess.run(["git", "clone", "--quiet", str(ROOT), str(dest)], check=True)


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _run(cmd: Sequence[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd), cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", check=False
    )


def _offline_env(clone: Path) -> dict[str, str]:
    """No key, no provider override, sockets blocked: what a reviewer without a key has."""
    env = {k: v for k, v in os.environ.items() if k not in {"GROQ_API_KEY", "DOCGATE_PROVIDER"}}
    env["PYTHONPATH"] = str(clone / NETBLOCK)
    env.pop("DOCGATE_NO_REEXEC", None)
    return env


def stage(name: str, ok: bool, detail: str, started: float) -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  {name:<8} {time.monotonic() - started:6.1f}s  {detail}")
    return ok


def verify(clone: Path) -> bool:
    py = venv_python(clone / ".venv")
    env = dict(os.environ)
    t = time.monotonic()
    made = _run([sys.executable, "-m", "venv", str(clone / ".venv")], clone, env)
    if not stage(
        "venv", made.returncode == 0, "" if made.returncode == 0 else made.stderr.strip()[-200:], t
    ):
        return False

    t = time.monotonic()
    setup = _run([str(py), "tasks.py", "setup"], clone, env)
    if not stage(
        "setup",
        setup.returncode == 0,
        "" if setup.returncode == 0 else setup.stderr.strip()[-300:],
        t,
    ):
        print(setup.stdout[-1500:])
        return False

    # Launched from the *system* Python on purpose: tasks.py must hand over to the project venv.
    t = time.monotonic()
    demo = _run([sys.executable, "tasks.py", "demo"], clone, _offline_env(clone))
    handed_over = ".venv" in demo.stderr
    detail = "" if demo.returncode == 0 else (demo.stderr.strip() or demo.stdout)[-400:]
    ok = demo.returncode == 0 and EXPECTED_SUMMARY in demo.stdout and handed_over
    if not stage("demo", ok, detail or "10 packs, no key, sockets blocked, venv handoff", t):
        return False

    t = time.monotonic()
    check = _run([str(py), "tasks.py", "check"], clone, env)
    tail = [ln for ln in check.stdout.splitlines() if "passed" in ln or "failed" in ln][-1:]
    if not stage("check", check.returncode == 0, " ".join(tail), t):
        print(check.stdout[-2500:])
        return False
    return True


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--worktree", action="store_true", help="copy the working tree, not HEAD")
    parser.add_argument("--keep", action="store_true", help="leave the temporary directory")
    args = parser.parse_args(argv)

    work = Path(tempfile.mkdtemp(prefix="docgate-fresh-"))
    clone = work / "clone"
    try:
        t = time.monotonic()
        if args.worktree:
            copy_worktree(clone)
        else:
            clone_head(clone)
        files = sum(1 for p in clone.rglob("*") if p.is_file())
        mode = "worktree copy" if args.worktree else "git clone of HEAD"
        stage("clone", True, f"{mode}: {files} files in {clone}", t)
        ok = verify(clone)
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)  # Windows may hold files briefly; best effort
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
