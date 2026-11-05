"""Assemble the API from settings, and run it. The only place the API touches configuration."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from fastapi import FastAPI

from docgate.api.app import create_app
from docgate.api.config import LOOPBACK_HOSTS, ApiConfig
from docgate.evaluation.golden import load_golden
from docgate.evaluation.mutations import DEFAULT_FILE as MUTATION_FILE
from docgate.settings import Settings
from docgate.workflow.evaluate import EvalService
from docgate.workflow.runs import RunManager
from docgate.workflow.wiring import build_deps

OPENAPI_FILE = Path("docs/openapi.json")


@dataclass(frozen=True)
class ServeOptions:
    sample_dir: Path = Path("data/sample")
    golden_file: Path = Path("data/golden/expected.json")
    mutation_file: Path = MUTATION_FILE
    db: Path = Path("runs/api.sqlite")  # its own file: never the CLI's or the demo's record
    out_dir: Path = Path("runs/api")
    web_dist: Path = Path("web/dist")
    host: str = "127.0.0.1"
    port: int = 8000
    step_delay_s: float = 0.0
    reviewer: str = "reviewer"


def is_loopback(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


def build_app(settings: Settings, opts: ServeOptions) -> FastAPI:
    """Raises SettingsError / LLMConfigError / PurchaseRequestError on a bad configuration, before
    any database file is created."""
    deps = build_deps(settings, opts.sample_dir)
    # The evaluation page always scores the recordings: it must never spend live requests.
    offline = replace(settings, provider="replay", groq_api_key=None)
    evaluator = EvalService(
        build_deps(offline, opts.sample_dir),
        _packs(opts.sample_dir),
        load_golden(opts.golden_file),
    )
    manager = RunManager(
        deps, _packs(opts.sample_dir), opts.db, out_dir=opts.out_dir, step_delay_s=opts.step_delay_s
    )
    hosts = LOOPBACK_HOSTS if is_loopback(opts.host) else (*LOOPBACK_HOSTS, opts.host)
    config = ApiConfig(
        web_dist=opts.web_dist,
        mutation_file=opts.mutation_file,
        provider=settings.provider,
        model=settings.groq_model if settings.provider == "groq" else None,
        host=opts.host,
        port=opts.port,
        allowed_hosts=hosts,
        default_reviewer=opts.reviewer,
    )
    return create_app(manager, config, evaluator)


def _packs(sample_dir: Path) -> dict[str, Path]:
    return {p.stem: p for p in sorted(sample_dir.glob("supplier-pack-*.pdf"))}


def openapi_text(settings: Settings, opts: ServeOptions) -> str:
    """The API contract as stable JSON, for the front end's type generator. Built on a throwaway
    database so generating it touches no real record."""
    with tempfile.TemporaryDirectory() as tmp:
        app = build_app(replace(settings, provider="replay"), replace(opts, db=Path(tmp) / "x.db"))
        try:
            schema = app.openapi()
        finally:
            app.state.services.manager.close()
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"
