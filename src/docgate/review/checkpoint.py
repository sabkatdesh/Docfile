"""Open the SQLite checkpointer. The only module that touches the checkpoint file."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

from docgate.compare.arithmetic import ArithmeticFinding
from docgate.compare.summary import Comparison
from docgate.domain.models import (
    DayRange,
    Decision,
    Extraction,
    FieldStatus,
    HumanReview,
    NodeError,
    PRLine,
    RuleResult,
    RuleStatus,
    Verdict,
)
from docgate.extraction.base import Candidate, ExtractorOutput, Outcome
from docgate.extraction.reconcile import FieldIssue
from docgate.reporting.report import PackReport

DEFAULT_DB = Path("runs/checkpoints.sqlite")

# Every type stored in PackState. LangGraph will refuse unlisted types in a future version, so
# a new state field of a new type must be added here (a test reads a full checkpoint to catch it).
_STATE_TYPES: tuple[type, ...] = (
    ArithmeticFinding,
    Candidate,
    Comparison,
    DayRange,
    Decision,
    Extraction,
    ExtractorOutput,
    FieldIssue,
    FieldStatus,
    HumanReview,
    NodeError,
    Outcome,
    PackReport,
    PRLine,
    RuleResult,
    RuleStatus,
    Verdict,
)


def _serde() -> JsonPlusSerializer:
    return JsonPlusSerializer(
        allowed_msgpack_modules=[(t.__module__, t.__qualname__) for t in _STATE_TYPES]
    )


@contextmanager
def sqlite_saver(path: Path) -> Iterator[SqliteSaver]:
    """Yield a saver and always close the connection (an open handle locks the file on Windows)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    try:
        yield SqliteSaver(conn, serde=_serde())
    finally:
        conn.close()
