"""Run the graph over many packs. Stops the batch on an operator problem, never on a bad pack."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from docgate.workflow.graph import run_pack
from docgate.workflow.state import PackState


class OperatorError(Exception):
    """A configuration problem (bad key, exhausted budget). Escalating every pack would hide it."""


def pack_number(pack_id: str) -> int:
    match = re.search(r"(\d+)$", pack_id)
    if not match:
        raise ValueError(f"cannot read a pack number from {pack_id!r}")
    return int(match.group(1))


def run_packs(graph: Any, paths: Sequence[Path]) -> list[PackState]:
    states: list[PackState] = []
    for path in paths:
        state = run_pack(graph, path.stem, path)
        config_errors = [e for e in state.get("errors", []) if e.kind == "config"]
        if config_errors:
            raise OperatorError("; ".join(f"{e.node}: {e.message}" for e in config_errors))
        states.append(state)
    return states
