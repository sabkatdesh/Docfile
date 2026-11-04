from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import groq
import httpx
import pytest

from docgate.llm.groq import GroqProvider
from docgate.llm.provider import (
    LLMBadResponseError,
    LLMConfigError,
    LLMRateLimitedError,
    LLMRequest,
    LLMServerError,
    LLMTimeoutError,
)

HTTP_REQ = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
SCHEMA = {"type": "object", "properties": {}}


def _req(**params: str) -> LLMRequest:
    base = {"reasoning_effort": "low", "structured_mode": "strict", "max_completion_tokens": "999"}
    return LLMRequest(
        system="SYS",
        user="USER",
        schema=SCHEMA,
        schema_name="extract",
        prompt_version="p",
        schema_version="v",
        params=base | params,
    )


class FakeClient:
    def __init__(self, result: str | Exception | None) -> None:
        self.kwargs: dict[str, Any] = {}
        self._result = result
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if isinstance(self._result, Exception):
            raise self._result
        msg = SimpleNamespace(content=self._result)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _status_error(cls: type[groq.APIStatusError], code: int, **headers: str) -> Exception:
    resp = httpx.Response(code, headers=headers, request=HTTP_REQ)
    return cls("boom", response=resp, body=None)


def test_strict_request_shape() -> None:
    client = FakeClient("{}")
    out = GroqProvider(client, "openai/gpt-oss-120b", timeout_s=30).complete_json(_req())
    assert out == "{}"
    k = client.kwargs
    assert k["model"] == "openai/gpt-oss-120b"
    assert k["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USER"},
    ]
    assert k["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "extract", "strict": True, "schema": SCHEMA},
    }
    assert k["reasoning_effort"] == "low"
    assert k["include_reasoning"] is False
    assert k["temperature"] == 0
    assert k["max_completion_tokens"] == 999
    assert k["timeout"] == 30


def test_best_effort_mode_turns_strict_off() -> None:
    client = FakeClient("{}")
    GroqProvider(client, "m", 30).complete_json(_req(structured_mode="best_effort"))
    assert client.kwargs["response_format"]["json_schema"]["strict"] is False


def test_json_object_mode_puts_the_schema_in_the_system_message() -> None:
    client = FakeClient("{}")
    GroqProvider(client, "m", 30).complete_json(_req(structured_mode="json_object"))
    assert client.kwargs["response_format"] == {"type": "json_object"}
    assert "JSON" in client.kwargs["messages"][0]["content"]
    assert '"properties"' in client.kwargs["messages"][0]["content"]


def test_empty_content_becomes_an_empty_string() -> None:
    assert GroqProvider(FakeClient(None), "m", 30).complete_json(_req()) == ""


def test_unknown_structured_mode_is_a_config_error() -> None:
    with pytest.raises(LLMConfigError):
        GroqProvider(FakeClient("{}"), "m", 30).complete_json(_req(structured_mode="magic"))


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (groq.APITimeoutError(request=HTTP_REQ), LLMTimeoutError),
        (groq.APIConnectionError(request=HTTP_REQ), LLMServerError),
        (_status_error(groq.InternalServerError, 500), LLMServerError),
        (_status_error(groq.APIStatusError, 503), LLMServerError),
        (_status_error(groq.AuthenticationError, 401), LLMConfigError),
        (_status_error(groq.PermissionDeniedError, 403), LLMConfigError),
        (_status_error(groq.NotFoundError, 404), LLMConfigError),
        (_status_error(groq.BadRequestError, 400), LLMBadResponseError),
        (_status_error(groq.UnprocessableEntityError, 422), LLMBadResponseError),
    ],
)
def test_sdk_errors_map_to_provider_errors(error: Exception, expected: type[Exception]) -> None:
    with pytest.raises(expected):
        GroqProvider(FakeClient(error), "m", 30).complete_json(_req())


def test_429_carries_retry_after() -> None:
    err = _status_error(groq.RateLimitError, 429, **{"retry-after": "7"})
    with pytest.raises(LLMRateLimitedError) as info:
        GroqProvider(FakeClient(err), "m", 30).complete_json(_req())
    assert info.value.retry_after == 7.0


def test_429_without_a_usable_header_has_no_retry_after() -> None:
    err = _status_error(groq.RateLimitError, 429, **{"retry-after": "soon"})
    with pytest.raises(LLMRateLimitedError) as info:
        GroqProvider(FakeClient(err), "m", 30).complete_json(_req())
    assert info.value.retry_after is None
