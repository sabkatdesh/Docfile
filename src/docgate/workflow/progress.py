"""Run one pack and report each node as it completes. The API's progress stream is built on this;
it runs the same graph as `run_pack`, only observed with LangGraph's "updates" stream."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docgate.workflow.state import PackState

INTERRUPT_KEY = "__interrupt__"


@dataclass(frozen=True)
class NodeDone:
    pack_id: str
    node: str
    ok: bool
    message: str | None
    elapsed_ms: int


@dataclass(frozen=True)
class Paused:
    """The pack reached the human gate; its verdict is Needs a person and no report exists yet."""

    pack_id: str
    state: PackState


@dataclass(frozen=True)
class Finished:
    pack_id: str
    state: PackState


PackProgress = NodeDone | Paused | Finished


def stream_pack(
    graph: Any,
    pack_id: str,
    pdf_path: Path,
    clock: Callable[[], float] = time.monotonic,
) -> Iterator[PackProgress]:
    config = {"configurable": {"thread_id": pack_id}}  # one thread per pack, as run_pack does
    started = clock()
    paused = False
    for chunk in graph.stream(
        {"pack_id": pack_id, "pdf_path": str(pdf_path), "errors": []}, config, stream_mode="updates"
    ):
        for node, update in chunk.items():
            if node == INTERRUPT_KEY:
                paused = True
                continue
            errors = (update or {}).get("errors") or []
            yield NodeDone(
                pack_id=pack_id,
                node=node,
                ok=not errors,
                message="; ".join(e.message for e in errors) or None,
                elapsed_ms=int((clock() - started) * 1000),
            )
    state: PackState = graph.get_state(config).values
    yield Paused(pack_id, state) if paused else Finished(pack_id, state)
