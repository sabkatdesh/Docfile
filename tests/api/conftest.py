"""Shared API fixtures: a real app over the real replay pipeline, on a database in tmp_path."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docgate.api.app import create_app
from docgate.api.config import ApiConfig
from docgate.evaluation.golden import load_golden
from docgate.workflow.deps import Deps
from docgate.workflow.evaluate import EvalService
from docgate.workflow.runs import RunManager
from tests.graph_support import ROOT, pack_path, replay_deps

PACKS = {f"supplier-pack-{n:02d}": pack_path(n) for n in range(1, 11)}
GOLDEN = ROOT / "data" / "golden" / "expected.json"
MUTATIONS = ROOT / "data" / "golden" / "mutation_results.json"
TEST_HOSTS = ("testserver", "localhost", "127.0.0.1", "[::1]")


class Built:
    def __init__(self, app: FastAPI, manager: RunManager, client: TestClient) -> None:
        self.app, self.manager, self.client = app, manager, client

    def run(self, packs: list[int] | None = None, **body: Any) -> str:
        """Start a run, read its whole (finite) event stream and return the run id."""
        res = self.client.post("/api/runs", json={"packs": packs, **body})
        assert res.status_code == 202, res.text
        run_id: str = res.json()["run_id"]
        self.client.get(res.json()["events_url"])  # returns once the run has finished
        return run_id


@pytest.fixture
def build(tmp_path: Path) -> Iterator[Callable[..., Built]]:
    opened: list[tuple[RunManager, TestClient]] = []

    def factory(
        deps: Deps | None = None,
        *,
        web_dist: Path | None = None,
        mutation_file: Path = MUTATIONS,
        raise_server_exceptions: bool = True,
        **config: Any,
    ) -> Built:
        manager = RunManager(deps or replay_deps(), PACKS, tmp_path / "api.sqlite")
        config.setdefault("allowed_hosts", TEST_HOSTS)
        cfg = ApiConfig(
            web_dist=web_dist or tmp_path / "no-dist",
            mutation_file=mutation_file,
            provider="replay",
            model=None,
            **config,
        )
        evaluator = EvalService(replay_deps(), PACKS, load_golden(GOLDEN))
        app = create_app(manager, cfg, evaluator)
        client = TestClient(app, raise_server_exceptions=raise_server_exceptions)
        opened.append((manager, client))
        return Built(app, manager, client)

    yield factory
    for manager, client in opened:
        client.close()
        manager.close()


def parse_sse(body: str) -> list[dict[str, Any]]:
    """Frames of a text/event-stream body: {"id", "event", "data"} (comments are skipped)."""
    frames: list[dict[str, Any]] = []
    for block in body.strip().split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in block.splitlines() if not line.startswith(":")
        )
        if fields:
            frames.append(
                {
                    "id": int(fields["id"]),
                    "event": fields["event"],
                    "data": json.loads(fields["data"]),
                }
            )
    return frames
