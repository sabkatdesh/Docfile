"""The review port: what a caller can ask about paused packs. No LangGraph in here."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from docgate.domain.models import Decision, HumanReview
from docgate.review.payload import ReviewPayload
from docgate.workflow.state import PackState


class ReviewError(Exception):
    """A review request that cannot be honoured. The message is shown to the operator as is."""


class UnknownPackError(ReviewError):
    pass


class NotReviewableError(ReviewError):
    pass


class AlreadyResolvedError(ReviewError):
    pass


class InvalidReviewError(ReviewError):
    pass


class ReviewKind(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    NOT_REVIEWABLE = "not reviewable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ReviewStatus:
    kind: ReviewKind
    pack_id: str
    machine_decision: Decision | None = None
    payload: ReviewPayload | None = None
    human_review: HumanReview | None = None


@dataclass(frozen=True)
class PendingReview:
    pack_id: str
    payload: ReviewPayload


class ReviewStore(Protocol):
    def pending(self) -> list[PendingReview]: ...

    def status(self, pack_id: str) -> ReviewStatus: ...

    def resolve(self, pack_id: str, decision: Decision, reason: str, reviewer: str) -> PackState:
        """Record the answer and finish the pack. Raises a `ReviewError`; never overwrites."""
        ...
