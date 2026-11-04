from __future__ import annotations

import json
import socket
from dataclasses import replace
from pathlib import Path

import pytest

from docgate.llm.provider import LLMBadResponseError, LLMError, LLMRequest
from docgate.llm.replay_provider import (
    RecordingProvider,
    ReplayMissError,
    ReplayProvider,
    request_key,
)
from tests.fakes import FakeProvider

REQ = LLMRequest(
    system="sys",
    user="doc text",
    schema={"type": "object"},
    schema_name="n",
    prompt_version="extract-v3",
    schema_version="wire-v1",
    params={"reasoning_effort": "low"},
    label="supplier-pack-04",
)
MODEL = "openai/gpt-oss-120b"


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)


def test_key_is_deterministic() -> None:
    assert request_key(REQ, MODEL) == request_key(replace(REQ), MODEL)


@pytest.mark.parametrize(
    "changed",
    [
        replace(REQ, user="other text"),
        replace(REQ, system="other prompt body"),
        replace(REQ, prompt_version="extract-v2"),
        replace(REQ, schema_version="wire-v2"),
        replace(REQ, params={"reasoning_effort": "high"}),
    ],
)
def test_key_changes_with_every_input(changed: LLMRequest) -> None:
    assert request_key(changed, MODEL) != request_key(REQ, MODEL)


def test_key_changes_with_the_model() -> None:
    assert request_key(REQ, MODEL) != request_key(REQ, "other-model")


def test_label_does_not_change_the_key() -> None:
    assert request_key(replace(REQ, label="x"), MODEL) == request_key(REQ, MODEL)


def test_record_then_replay_returns_the_same_raw_response(tmp_path: Path) -> None:
    rec = RecordingProvider(FakeProvider(['{"a": 1}'], model_id=MODEL), tmp_path)
    assert rec.complete_json(REQ) == '{"a": 1}'
    (path,) = rec.written
    assert path.name.startswith("supplier-pack-04__")
    stored = json.loads(path.read_text("utf-8"))
    assert stored["response"] == '{"a": 1}'
    assert stored["model"] == MODEL
    assert stored["key"] == request_key(REQ, MODEL)
    assert ReplayProvider(tmp_path, MODEL).complete_json(REQ) == '{"a": 1}'


def test_replay_is_deterministic_and_never_touches_the_network(
    tmp_path: Path, no_network: None
) -> None:
    RecordingProvider(FakeProvider(["raw"], model_id=MODEL), tmp_path).complete_json(REQ)
    replay = ReplayProvider(tmp_path, MODEL)
    assert [replay.complete_json(REQ) for _ in range(3)] == ["raw"] * 3


def test_replay_miss_is_a_clear_non_retryable_error(tmp_path: Path) -> None:
    with pytest.raises(ReplayMissError, match="record"):
        ReplayProvider(tmp_path, MODEL).complete_json(REQ)
    assert issubclass(ReplayMissError, LLMError)
    assert not issubclass(ReplayMissError, LLMBadResponseError)


def test_replay_for_a_different_model_misses(tmp_path: Path) -> None:
    RecordingProvider(FakeProvider(["raw"], model_id=MODEL), tmp_path).complete_json(REQ)
    with pytest.raises(ReplayMissError):
        ReplayProvider(tmp_path, "other-model").complete_json(REQ)


def test_recording_reads_through_instead_of_calling_again(tmp_path: Path) -> None:
    inner = FakeProvider(["first", "second"], model_id=MODEL)
    rec = RecordingProvider(inner, tmp_path)
    assert rec.complete_json(REQ) == "first"
    assert rec.complete_json(REQ) == "first"
    assert inner.calls == 1


def test_overwrite_calls_the_model_again(tmp_path: Path) -> None:
    inner = FakeProvider(["first", "second"], model_id=MODEL)
    RecordingProvider(inner, tmp_path).complete_json(REQ)
    forced = RecordingProvider(inner, tmp_path, overwrite=True)
    assert forced.complete_json(REQ) == "second"
    assert ReplayProvider(tmp_path, MODEL).complete_json(REQ) == "second"


def test_discard_removes_what_this_run_wrote(tmp_path: Path) -> None:
    rec = RecordingProvider(FakeProvider(["x"], model_id=MODEL), tmp_path)
    rec.complete_json(REQ)
    rec.discard_written()
    assert list(tmp_path.glob("*.json")) == []
