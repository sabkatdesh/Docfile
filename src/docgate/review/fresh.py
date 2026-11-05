"""Start a run from an empty checkpoint database, without ever discarding a waiting review."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from docgate.review.store import ReviewError


def database_files(db: Path) -> list[Path]:
    """The database and the SQLite side files that can sit next to it."""
    return [db, Path(f"{db}-wal"), Path(f"{db}-shm")]


def discard(db: Path) -> None:
    for path in database_files(db):
        path.unlink(missing_ok=True)


def start_fresh(db: Path, pending_packs: Callable[[], Sequence[str]]) -> None:
    """Remove an old database so a leftover cannot change this run's result.

    Refuses, and changes nothing, while any pack still waits for a person: that decision would
    be lost. `pending_packs` is only called when a database exists.
    """
    if not db.exists():
        return
    waiting = pending_packs()
    if waiting:
        raise ReviewError(
            f"{db} still holds {len(waiting)} pack(s) waiting for a decision "
            f"({', '.join(waiting)}). Resolve them, use --resume to continue that record, "
            "or delete the file yourself."
        )
    discard(db)
