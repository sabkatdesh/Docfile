"""Request and response envelopes. The pack, review and evaluation models are the pure ones from
`workflow`, `review` and `evaluation`; the OpenAPI schema M6 generates its types from is the sum."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from docgate.domain.models import Decision
from docgate.review.payload import ReviewPayload


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorBody(BaseModel):
    """Every non-2xx response has this shape."""

    error: ErrorDetail


class Health(BaseModel):
    status: str
    provider: str
    model: str | None
    packs: int
    web_built: bool
    active_run_id: str | None


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packs: list[int] | None = None  # pack numbers; null runs all of them
    resume: bool = False  # keep the record and skip packs already on it
    discard_pending: bool = False  # allow a fresh run to drop reviews still waiting


class RunAccepted(BaseModel):
    run_id: str
    packs: list[str]
    events_url: str


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Decision  # Approve or Reject; the domain refuses anything else
    reason: str  # the domain refuses a blank one
    reviewer: str | None = None


class PendingReviewItem(BaseModel):
    pack_id: str
    payload: ReviewPayload
