"""Probes found in the M5.5 audit: reads while a run writes, and secrets in logs."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

import pytest

from tests.api.conftest import Built

Build = Callable[..., Built]


def test_reads_during_a_run_never_fail(build: Build) -> None:
    b = build()
    res = b.client.post("/api/runs", json={})
    assert res.status_code == 202
    failures: list[str] = []
    stop = threading.Event()

    def poll() -> None:
        while not stop.is_set():
            for url in ("/api/packs", "/api/review", "/api/health"):
                got = b.client.get(url)
                if got.status_code != 200:
                    failures.append(f"{url} {got.status_code} {got.text[:80]}")

    poller = threading.Thread(target=poll)
    poller.start()
    b.client.get(res.json()["events_url"])  # blocks until run_finished
    stop.set()
    poller.join(10)
    assert failures == []
    assert len(b.client.get("/api/packs").json()) == 10


def test_an_unexpected_error_logs_its_type_but_never_its_message(
    build: Build, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "gsk_TOPSECRET_do_not_leak"
    b = build(raise_server_exceptions=False)

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError(f"auth failed for {secret}")

    b.manager.state = boom  # type: ignore[method-assign]
    with caplog.at_level(logging.DEBUG):
        res = b.client.get("/api/packs")
    assert res.status_code == 500
    assert secret not in res.text
    assert secret not in caplog.text
