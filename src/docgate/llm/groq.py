"""Groq adapter. Thin on purpose: it maps requests and errors, and holds no retry logic."""

from __future__ import annotations

import json
from typing import Any

import groq

from docgate.llm.provider import (
    LLMBadResponseError,
    LLMConfigError,
    LLMError,
    LLMRateLimitedError,
    LLMRequest,
    LLMServerError,
    LLMTimeoutError,
)

_CONFIG_STATUSES = {401, 403, 404}
_BAD_REQUEST_STATUSES = {400, 422}


def make_client(api_key: str) -> groq.Groq:
    # max_retries=0: RetryingProvider is the only retry policy, so attempts are counted honestly.
    return groq.Groq(api_key=api_key, max_retries=0)


class GroqProvider:
    def __init__(self, client: Any, model_id: str, timeout_s: float) -> None:
        self._client = client
        self.model_id = model_id
        self._timeout_s = timeout_s

    def complete_json(self, request: LLMRequest) -> str:
        kwargs = self._kwargs(request)
        try:
            response = self._client.chat.completions.create(**kwargs)
        except groq.APITimeoutError as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except groq.APIConnectionError as exc:
            raise LLMServerError(f"connection error: {exc}") from exc
        except groq.APIStatusError as exc:
            raise _map_status(exc) from exc
        content = response.choices[0].message.content
        return content or ""

    def _kwargs(self, request: LLMRequest) -> dict[str, Any]:
        p = request.params
        mode = p.get("structured_mode", "strict")
        system = request.system
        if mode in ("strict", "best_effort"):
            response_format: dict[str, Any] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": mode == "strict",
                    "schema": request.schema,
                },
            }
        elif mode == "json_object":
            response_format = {"type": "json_object"}
            system += "\n\nRespond with a JSON object matching this JSON Schema:\n" + json.dumps(
                request.schema
            )
        else:
            raise LLMConfigError(f"unknown structured_mode {mode!r}")
        return {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": request.user},
            ],
            "response_format": response_format,
            "temperature": 0,
            "reasoning_effort": p.get("reasoning_effort", "low"),
            "include_reasoning": False,
            "max_completion_tokens": int(p.get("max_completion_tokens", "4096")),
            "timeout": self._timeout_s,
        }


def _map_status(exc: groq.APIStatusError) -> LLMError:
    code = exc.status_code
    if code == 429:
        return LLMRateLimitedError(f"rate limited: {exc}", retry_after=_retry_after(exc))
    if code in _CONFIG_STATUSES:
        return LLMConfigError(f"HTTP {code}: {exc}")
    if code in _BAD_REQUEST_STATUSES:
        return LLMBadResponseError(f"HTTP {code}: {exc}")
    if code >= 500 or code in (408, 409):
        return LLMServerError(f"HTTP {code}: {exc}")
    return LLMBadResponseError(f"HTTP {code}: {exc}")


def _retry_after(exc: groq.APIStatusError) -> float | None:
    raw = exc.response.headers.get("retry-after")
    try:
        return float(raw) if raw is not None else None
    except ValueError:
        return None
