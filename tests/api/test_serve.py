"""Assembling the API from settings, the `serve` command's failure modes, and the contracts that
are committed to the repository (OpenAPI for the front end, mutation results for the page)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from scripts.mutation_report import build_results

from docgate.api.serve import OPENAPI_FILE, ServeOptions, build_app, is_loopback, openapi_text
from docgate.cli import main
from docgate.evaluation.mutations import DEFAULT_FILE, render_results
from docgate.settings import MissingApiKeyError, Settings
from tests.graph_support import RECORDED, ROOT


def opts(tmp: Path, **kw: Any) -> ServeOptions:
    base = ServeOptions(
        sample_dir=ROOT / "data" / "sample",
        golden_file=ROOT / "data" / "golden" / "expected.json",
        mutation_file=ROOT / DEFAULT_FILE,
        db=tmp / "api.sqlite",
        out_dir=tmp / "reports",
        web_dist=tmp / "dist",
    )
    return replace(base, **kw)


def replay_settings() -> Settings:
    return Settings(recorded_dir=RECORDED)


def test_built_app_serves_real_data_in_replay_mode(tmp_path: Path) -> None:
    app = build_app(replay_settings(), opts(tmp_path, reviewer="the-operator"))
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/health").json()["provider"] == "replay"
        assert len(client.get("/api/packs").json()) == 10
        assert client.get("/api/eval").json()["golden"]["correct"] == 10
    assert (tmp_path / "api.sqlite").is_file()  # its own record, not the CLI's


def test_live_mode_without_a_key_refuses_before_creating_anything(tmp_path: Path) -> None:
    live = replace(replay_settings(), provider="groq", groq_api_key=None)
    with pytest.raises(MissingApiKeyError, match="GROQ_API_KEY"):
        build_app(live, opts(tmp_path))
    assert not (tmp_path / "api.sqlite").exists()


def test_serve_command_reports_a_missing_key_readably(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env here
    assert main(["serve", "--provider", "groq", "--db", str(tmp_path / "x.sqlite")]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error:") and "GROQ_API_KEY" in err and "Traceback" not in err


def test_loopback_detection() -> None:
    assert is_loopback("127.0.0.1") and is_loopback("localhost") and is_loopback("::1")
    assert not is_loopback("0.0.0.0") and not is_loopback("192.168.1.5")


def test_a_non_loopback_host_is_added_to_the_allowed_hosts(tmp_path: Path) -> None:
    app = build_app(replay_settings(), opts(tmp_path, host="192.168.1.5"))
    assert "192.168.1.5" in app.state.services.config.allowed_hosts
    app.state.services.manager.close()


def test_committed_openapi_matches_the_code() -> None:
    """The file M6 generates TypeScript types from must not drift from the routes."""
    committed = (ROOT / OPENAPI_FILE).read_text(encoding="utf-8")
    assert committed == openapi_text(replay_settings(), ServeOptions())


def test_every_route_has_a_declared_response_model() -> None:
    import json

    schema = json.loads((ROOT / OPENAPI_FILE).read_text(encoding="utf-8"))
    for path, ops in schema["paths"].items():
        for method, op in ops.items():
            ok = [c for c in op["responses"] if c.startswith("2")]
            assert ok, (method, path)
            if path.endswith("/events") or path.endswith("/pdf"):
                continue  # a stream and a file have no JSON model
            content = op["responses"][ok[0]]["content"]["application/json"]["schema"]
            assert content, (method, path)
    assert "ErrorBody" in schema["components"]["schemas"]


def test_committed_mutation_results_are_current() -> None:
    committed = (ROOT / DEFAULT_FILE).read_text(encoding="utf-8")
    assert committed == render_results(build_results())
    assert all(c.ok for c in build_results().cases)
