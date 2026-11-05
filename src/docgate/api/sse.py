"""Server-sent events framing and the blocking read loop over a run's event log."""

from __future__ import annotations

import json
from collections.abc import Iterator

from docgate.workflow.runs import RunEvent, RunManager

KEEPALIVE = ": keep-alive\n\n"


def frame(event: RunEvent) -> str:
    payload = {**event.data, "seq": event.seq, "ts": event.ts}
    return f"id: {event.seq}\nevent: {event.type}\ndata: {json.dumps(payload)}\n\n"


def parse_last_event_id(value: str | None) -> int:
    """Where to resume. Anything unreadable means "from the start"."""
    try:
        return max(int(value), 0) if value is not None else 0
    except ValueError:
        return 0


def stream(manager: RunManager, run_id: str, after: int, keepalive_s: float) -> Iterator[str]:
    """Frames until the run is over. The stream is finite, so a client always sees the end."""
    while True:
        events, finished = manager.events_after(run_id, after, timeout=keepalive_s)
        for event in events:
            yield frame(event)
            after = event.seq
        if finished:
            return
        if not events:
            yield KEEPALIVE  # keeps proxies from closing an idle connection
