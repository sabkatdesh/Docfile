"""Thin handlers: parse, delegate to the workflow, return a typed model. No judging here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import FileResponse, StreamingResponse

from docgate.api.config import ApiConfig
from docgate.api.errors import ApiError
from docgate.api.schemas import (
    ErrorBody,
    Health,
    PendingReviewItem,
    ReviewRequest,
    RunAccepted,
    RunRequest,
)
from docgate.api.sse import parse_last_event_id, stream
from docgate.evaluation.mutations import mutation_view
from docgate.evaluation.view import EvalView, build_golden_view
from docgate.workflow.detail import PackDetail, PackListItem, build_detail, build_list_item
from docgate.workflow.evaluate import EvalService
from docgate.workflow.runner import pack_number
from docgate.workflow.runs import RunManager

ERR = {"model": ErrorBody}


@dataclass(frozen=True)
class Services:
    manager: RunManager
    config: ApiConfig
    evaluator: EvalService


def services(request: Request) -> Services:
    svc: Services = request.app.state.services
    return svc


Svc = Depends(services)
router = APIRouter(prefix="/api")


def _listed(svc: Services, pack_id: str) -> Any:
    path = svc.manager.pack_path(pack_id)
    if path is None:
        raise ApiError(404, "unknown_pack", f"unknown pack {pack_id!r}")
    return path


def _item(svc: Services, pack_id: str) -> PackListItem:
    path = _listed(svc, pack_id)
    return build_list_item(pack_id, path.name, svc.manager.state(pack_id))


@router.get("/health", response_model=Health)
def health(svc: Services = Svc) -> Health:
    return Health(
        status="ok",
        provider=svc.config.provider,
        model=svc.config.model,
        packs=len(svc.manager.pack_ids),
        web_built=(svc.config.web_dist / "index.html").is_file(),
        active_run_id=svc.manager.active_run_id,
    )


@router.get("/packs", response_model=list[PackListItem])
def list_packs(svc: Services = Svc) -> list[PackListItem]:
    return [_item(svc, pack_id) for pack_id in svc.manager.pack_ids]


@router.get("/packs/{pack_id}", response_model=PackDetail, responses={404: ERR})
def pack_detail(pack_id: str, svc: Services = Svc) -> PackDetail:
    _listed(svc, pack_id)
    state = svc.manager.state(pack_id)
    if state is None or "verdict" not in state:
        raise ApiError(404, "no_result", f"{pack_id} has not been run yet; start a run first")
    return build_detail(state)


@router.get(
    "/packs/{pack_id}/pdf",
    response_class=FileResponse,
    responses={200: {"content": {"application/pdf": {}}}, 404: ERR},
)
def pack_pdf(pack_id: str, svc: Services = Svc) -> FileResponse:
    path = _listed(svc, pack_id)  # looked up in the allowlist; never built from the request
    return FileResponse(
        path, media_type="application/pdf", filename=path.name, content_disposition_type="inline"
    )


@router.post(
    "/runs", response_model=RunAccepted, status_code=202, responses={404: ERR, 409: ERR, 422: ERR}
)
def start_run(body: RunRequest, svc: Services = Svc) -> RunAccepted:
    info = svc.manager.start(body.packs, resume=body.resume, discard_pending=body.discard_pending)
    return RunAccepted(
        run_id=info.run_id, packs=info.packs, events_url=f"/api/runs/{info.run_id}/events"
    )


@router.get(
    "/runs/{run_id}/events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}, 404: ERR},
)
def run_events(
    run_id: str,
    svc: Services = Svc,
    last_event_id: str | None = Header(default=None),
) -> StreamingResponse:
    if not svc.manager.has_run(run_id):  # before the response starts, so it can still be a 404
        raise ApiError(404, "unknown_run", f"unknown run {run_id!r}")
    frames = stream(
        svc.manager, run_id, parse_last_event_id(last_event_id), svc.config.sse_keepalive_s
    )
    return StreamingResponse(
        frames,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/review", response_model=list[PendingReviewItem])
def pending_reviews(svc: Services = Svc) -> list[PendingReviewItem]:
    return [PendingReviewItem(pack_id=p.pack_id, payload=p.payload) for p in svc.manager.pending()]


@router.post(
    "/review/{pack_id}",
    response_model=PackListItem,
    responses={404: ERR, 409: ERR, 422: ERR},
)
def resolve_review(pack_id: str, body: ReviewRequest, svc: Services = Svc) -> PackListItem:
    svc.manager.resolve(
        pack_id, body.decision, body.reason, body.reviewer or svc.config.default_reviewer
    )
    return _item(svc, pack_id)


@router.get("/eval", response_model=EvalView)
def evaluation(svc: Services = Svc) -> EvalView:
    human = {
        pack_number(s["pack_id"]): s["verdict"].human_decision
        for s in svc.manager.states()
        if "verdict" in s
    }
    return EvalView(
        golden=build_golden_view(svc.evaluator.result(), human),
        mutation=mutation_view(svc.config.mutation_file),
    )
