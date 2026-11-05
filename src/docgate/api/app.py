"""Application factory. Everything it needs is passed in, so a test or `serve` builds its own."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from docgate.api.config import ApiConfig
from docgate.api.errors import ApiError, install_error_handlers
from docgate.api.routes import Services, router, services
from docgate.workflow.evaluate import EvalService
from docgate.workflow.runs import RunManager

NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>docgate</title>
<body style="font-family:system-ui;max-width:40rem;margin:3rem auto;line-height:1.5">
<h1>docgate API is running</h1>
<p>The web front end is not built yet, so there is nothing to show here. Build it with
<code>npm --prefix web run build</code> and reload this page.</p>
<p>The API itself works: see <a href="/docs">/docs</a> for every endpoint.</p></body>"""


def _static(request: Request, full_path: str) -> Any:
    """The built front end, with a fallback to index.html for client-side routes."""
    if full_path == "api" or full_path.startswith("api/"):
        raise ApiError(404, "not_found", f"no such endpoint: /{full_path}")  # never the HTML page
    dist = services(request).config.web_dist
    index = dist / "index.html"
    if not index.is_file():
        if full_path == "":
            return HTMLResponse(NOT_BUILT)
        raise ApiError(404, "not_found", f"no such page: /{full_path}")
    try:
        candidate = (dist / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(dist.resolve()):
            return FileResponse(candidate)
    except (OSError, ValueError):
        pass  # an odd path is not a file; fall through to the app shell
    return FileResponse(index)


def create_app(manager: RunManager, config: ApiConfig, evaluator: EvalService) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        manager.close()

    app = FastAPI(
        title="docgate API",
        version="0.1.0",
        description="Supplier quotation checker. The LLM reads, code judges.",
        lifespan=lifespan,
    )
    app.state.services = Services(manager, config, evaluator)
    install_error_handlers(app)
    app.include_router(router)
    app.add_api_route("/{full_path:path}", _static, methods=["GET"], include_in_schema=False)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Last-Event-ID"],
        allow_credentials=False,
    )
    # Added last, so it runs first: a foreign Host is refused before anything else sees it.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(config.allowed_hosts))
    return app
