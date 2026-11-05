"""`ReviewStore` over the compiled graph and its checkpointer (thread id = pack id)."""

from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from pydantic import ValidationError

from docgate.domain.models import Decision, HumanReview
from docgate.review.payload import ReviewPayload
from docgate.review.store import (
    AlreadyResolvedError,
    InvalidReviewError,
    NotReviewableError,
    PendingReview,
    ReviewKind,
    ReviewStatus,
    UnknownPackError,
)
from docgate.workflow.state import PackState

Clock = Callable[[], datetime.datetime]


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _config(pack_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": pack_id}}


def _invalid(exc: ValidationError) -> InvalidReviewError:
    parts = [
        f"{'.'.join(str(p) for p in e['loc'])}: {e['msg'].removeprefix('Value error, ')}"
        for e in exc.errors()
    ]
    return InvalidReviewError("invalid review (" + "; ".join(parts) + ")")


class GraphReviewStore:
    def __init__(self, graph: Any, saver: BaseCheckpointSaver[Any], clock: Clock = utc_now) -> None:
        self._graph = graph
        self._saver = saver
        self._clock = clock

    def pack_ids(self) -> list[str]:
        found = {c.config["configurable"]["thread_id"] for c in self._saver.list(None)}
        return sorted(found)

    def status(self, pack_id: str) -> ReviewStatus:
        if pack_id not in self.pack_ids():
            return ReviewStatus(ReviewKind.UNKNOWN, pack_id)
        snapshot = self._graph.get_state(_config(pack_id))
        values = snapshot.values
        verdict = values.get("verdict")
        machine = verdict.decision if verdict else None
        for task in snapshot.tasks:
            for interrupt in task.interrupts:
                payload = ReviewPayload.model_validate(interrupt.value)
                return ReviewStatus(ReviewKind.PENDING, pack_id, machine, payload=payload)
        review = values.get("human_review")
        if review is not None:
            return ReviewStatus(ReviewKind.RESOLVED, pack_id, machine, human_review=review)
        return ReviewStatus(ReviewKind.NOT_REVIEWABLE, pack_id, machine)

    def states(self) -> list[PackState]:
        """The latest state of every pack on record, finished or paused."""
        return [self._graph.get_state(_config(i)).values for i in self.pack_ids()]

    def state(self, pack_id: str) -> PackState | None:
        """The latest state of one pack, or None when it has never been run."""
        if pack_id not in self.pack_ids():
            return None
        values: PackState = self._graph.get_state(_config(pack_id)).values
        return values

    def pending(self) -> list[PendingReview]:
        out: list[PendingReview] = []
        for pack_id in self.pack_ids():
            s = self.status(pack_id)
            if s.kind is ReviewKind.PENDING and s.payload is not None:
                out.append(PendingReview(pack_id, s.payload))
        return out

    def resolve(self, pack_id: str, decision: Decision, reason: str, reviewer: str) -> PackState:
        # Every check runs before the graph is touched, so a refused request changes nothing.
        try:
            review = HumanReview(
                decision=decision, reason=reason, reviewer=reviewer, reviewed_at=self._clock()
            )
        except ValidationError as exc:
            raise _invalid(exc) from exc
        status = self.status(pack_id)
        if status.kind is ReviewKind.UNKNOWN:
            known = ", ".join(self.pack_ids()) or "none"
            raise UnknownPackError(f"unknown pack {pack_id!r} (packs on record: {known})")
        if status.kind is ReviewKind.RESOLVED and status.human_review is not None:
            prev = status.human_review
            raise AlreadyResolvedError(
                f"{pack_id} was already resolved by {prev.reviewer}: {prev.decision.value} at "
                f"{prev.reviewed_at.isoformat()}; the first decision is kept"
            )
        if status.kind is ReviewKind.NOT_REVIEWABLE:
            shown = status.machine_decision.value if status.machine_decision else "no verdict"
            raise NotReviewableError(
                f"{pack_id} was decided automatically ({shown}); that decision is final "
                "and only 'Needs a person to check' packs are reviewed"
            )
        final: PackState = self._graph.invoke(
            Command(resume=review.model_dump(mode="json")), _config(pack_id)
        )
        return final
