"""One error shape for every failure: {"error": {"code", "message", "details"}}.

Domain exceptions keep their own messages (they are written for the operator); this module only
chooses the HTTP status and a stable code the front end can switch on.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from docgate.review.store import (
    AlreadyResolvedError,
    InvalidReviewError,
    NotReviewableError,
    ReviewError,
    UnknownPackError,
)
from docgate.settings import SettingsError
from docgate.workflow.runs import (
    PendingReviewsError,
    RunError,
    RunInProgressError,
    UnknownPackNumberError,
    UnknownRunError,
)

log = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(
        self, status: int, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def _respond(status: int, code: str, message: str, details: dict[str, Any] | None = None) -> Any:
    return JSONResponse(status_code=status, content=body(code, message, details))


_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}


def _classify(exc: Exception) -> tuple[int, str, dict[str, Any] | None] | None:
    """Status, code and details for a domain exception; None for anything unexpected."""
    if isinstance(exc, UnknownPackError):
        return 404, "unknown_pack", None
    if isinstance(exc, AlreadyResolvedError):
        return 409, "already_resolved", None
    if isinstance(exc, NotReviewableError):
        return 409, "machine_final", None
    if isinstance(exc, InvalidReviewError):
        return 422, "invalid_review", None
    if isinstance(exc, RunInProgressError):
        return 409, "run_in_progress", {"run_id": exc.run_id}
    if isinstance(exc, PendingReviewsError):
        return 409, "pending_reviews_would_be_lost", {"pack_ids": exc.pack_ids}
    if isinstance(exc, UnknownPackNumberError):
        return 404, "unknown_pack_number", None
    if isinstance(exc, UnknownRunError):
        return 404, "unknown_run", None
    if isinstance(exc, ReviewError | RunError):
        return 409, "conflict", None
    return None


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError) -> Any:
        return _respond(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(ReviewError)
    @app.exception_handler(RunError)
    async def domain_error(_: Request, exc: Exception) -> Any:
        status, code, details = _classify(exc) or (500, "internal_error", None)
        return _respond(status, code, str(exc), details)

    @app.exception_handler(SettingsError)
    async def settings_error(_: Request, exc: SettingsError) -> Any:
        return _respond(500, "configuration_error", str(exc))  # readable; never holds a key

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> Any:
        problems = [
            {"where": ".".join(str(p) for p in e["loc"]), "problem": e["msg"]} for e in exc.errors()
        ]
        return _respond(422, "validation_error", "the request is not valid", {"problems": problems})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> Any:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        return _respond(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception) -> Any:
        log.error("unhandled %s on a request", type(exc).__name__)  # type only: no values, no keys
        return _respond(500, "internal_error", "something went wrong on the server")
