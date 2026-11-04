"""Load the hand-written golden verdicts. Nothing here ever reads system output."""

from __future__ import annotations

import json
from pathlib import Path

from docgate.domain.models import Decision


class GoldenError(Exception):
    """The golden file is missing, malformed or empty."""


def load_golden(path: Path) -> dict[int, Decision]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        table = raw["expected"]
        golden = {int(pack): Decision(verdict) for pack, verdict in table.items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise GoldenError(f"invalid golden file {path}: {exc}") from exc
    if not golden:
        raise GoldenError(f"golden file {path} has no packs")
    return golden
