from __future__ import annotations

from pathlib import Path

import pytest

from docgate.extraction.factory import build_llm_stack
from docgate.llm.replay_provider import RecordingProvider, ReplayProvider
from docgate.llm.retry import RetryingProvider
from docgate.settings import MissingApiKeyError, load_settings


def test_replay_is_the_default_and_needs_no_key(tmp_path: Path) -> None:
    stack = build_llm_stack(load_settings({"DOCGATE_RECORDED_DIR": str(tmp_path)}))
    assert stack.live is None
    assert stack.recorder is None
    assert isinstance(stack.extractor._provider, ReplayProvider)


def test_groq_mode_wraps_the_client_in_the_retry_policy() -> None:
    stack = build_llm_stack(load_settings({"DOCGATE_PROVIDER": "groq", "GROQ_API_KEY": "gsk_x"}))
    assert isinstance(stack.extractor._provider, RetryingProvider)
    assert stack.live is stack.extractor._provider


def test_groq_mode_without_a_key_fails_before_any_client_exists() -> None:
    with pytest.raises(MissingApiKeyError):
        build_llm_stack(load_settings({"DOCGATE_PROVIDER": "groq"}))


def test_record_mode_works_even_when_provider_is_replay_but_needs_a_key() -> None:
    with pytest.raises(MissingApiKeyError):
        build_llm_stack(load_settings({}), record=True)
    stack = build_llm_stack(load_settings({"GROQ_API_KEY": "gsk_x"}), record=True)
    assert isinstance(stack.recorder, RecordingProvider)
    assert isinstance(stack.live, RetryingProvider)
