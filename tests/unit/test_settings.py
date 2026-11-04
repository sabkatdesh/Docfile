from __future__ import annotations

from pathlib import Path

import pytest

from docgate.settings import (
    MissingApiKeyError,
    SettingsError,
    load_settings,
    parse_env_file,
    request_params,
)


def test_defaults_are_replay_with_no_key_needed() -> None:
    s = load_settings({})
    assert s.provider == "replay"
    assert s.groq_model == "openai/gpt-oss-120b"
    assert s.reasoning_effort == "low"
    assert s.structured_mode == "strict"
    assert s.recorded_dir == Path("data/recorded")
    assert s.groq_api_key is None


def test_groq_mode_without_a_key_names_the_fix_and_never_prints_a_key() -> None:
    s = load_settings({"DOCGATE_PROVIDER": "groq"})
    with pytest.raises(MissingApiKeyError) as info:
        s.require_api_key()
    assert "GROQ_API_KEY" in str(info.value)
    assert ".env.example" in str(info.value)
    assert "DOCGATE_PROVIDER=replay" in str(info.value)


def test_blank_key_counts_as_missing() -> None:
    s = load_settings({"DOCGATE_PROVIDER": "groq", "GROQ_API_KEY": "   "})
    with pytest.raises(MissingApiKeyError):
        s.require_api_key()


def test_key_is_returned_but_hidden_from_repr() -> None:
    s = load_settings({"DOCGATE_PROVIDER": "groq", "GROQ_API_KEY": "gsk_secret_value"})
    assert s.require_api_key() == "gsk_secret_value"
    assert "gsk_secret_value" not in repr(s)


@pytest.mark.parametrize(
    "env",
    [
        {"DOCGATE_PROVIDER": "bedrock"},
        {"DOCGATE_REASONING_EFFORT": "extreme"},
        {"DOCGATE_STRUCTURED_MODE": "yolo"},
    ],
)
def test_invalid_choices_are_rejected(env: dict[str, str]) -> None:
    with pytest.raises(SettingsError):
        load_settings(env)


def test_request_params_are_the_behavioural_settings() -> None:
    params = request_params(load_settings({"DOCGATE_REASONING_EFFORT": "medium"}))
    assert params["reasoning_effort"] == "medium"
    assert params["structured_mode"] == "strict"
    assert "GROQ_API_KEY" not in params


def test_env_file_parser() -> None:
    text = '# comment\n\nA=1\nB = two words \nC=\nQ="quoted"\nbad line\n'
    assert parse_env_file(text) == {"A": "1", "B": "two words", "C": "", "Q": "quoted"}
