"""The seam between extraction and whichever model serves it. Groq, replay or a fake."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMRequest:
    system: str
    user: str
    schema: Mapping[str, Any]
    schema_name: str
    prompt_version: str
    schema_version: str
    # Everything that changes the model's behaviour (effort, mode, ...) so it is part of the key.
    params: Mapping[str, str]
    label: str = ""  # human-readable name for recordings, e.g. "supplier-pack-04"


class LLMProvider(Protocol):
    @property
    def model_id(self) -> str: ...

    def complete_json(self, request: LLMRequest) -> str:
        """Return the model's raw response text. Parsing and validation are the caller's job."""
        ...


class LLMError(Exception):
    """Base for every provider failure the pipeline knows how to handle."""


class LLMTimeoutError(LLMError):
    pass


class LLMServerError(LLMError):
    """5xx, connection failure or similar. Worth retrying."""


class LLMRateLimitedError(LLMError):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMBadResponseError(LLMError):
    """The provider rejected the request or the output was unusable (e.g. HTTP 400)."""


class LLMConfigError(LLMError):
    """Bad key, unknown model, exhausted request budget. An operator problem: stop the run."""


class LLMUnavailableError(LLMError):
    """Retries are exhausted. The caller escalates the pack; it never guesses."""


RETRYABLE: tuple[type[LLMError], ...] = (LLMTimeoutError, LLMServerError, LLMRateLimitedError)
