"""Backoff, pacing and a request budget around any provider. The only retry policy in the app."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from docgate.llm.provider import (
    RETRYABLE,
    LLMConfigError,
    LLMProvider,
    LLMRateLimitedError,
    LLMRequest,
    LLMUnavailableError,
)


class Clock(Protocol):
    def sleep(self, seconds: float) -> None: ...

    def monotonic(self) -> float: ...


class SystemClock:
    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def monotonic(self) -> float:
        return time.monotonic()


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_s: float = 2.0
    max_delay_s: float = 30.0
    # A longer retry-after usually means a daily cap; waiting it out would hang the run.
    retry_after_cap_s: float = 60.0
    min_interval_s: float = 0.0  # spacing between requests, for per-minute token limits
    max_requests: int | None = None


class RetryingProvider:
    def __init__(self, inner: LLMProvider, clock: Clock, policy: RetryPolicy) -> None:
        self._inner = inner
        self._clock = clock
        self._policy = policy
        self._last_start: float | None = None
        self.requests_made = 0

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    def complete_json(self, request: LLMRequest) -> str:
        p = self._policy
        for attempt in range(1, p.max_attempts + 1):
            self._pace_and_count()
            try:
                return self._inner.complete_json(request)
            except RETRYABLE as exc:
                delay = min(p.base_delay_s * 2 ** (attempt - 1), p.max_delay_s)
                if isinstance(exc, LLMRateLimitedError) and exc.retry_after is not None:
                    if exc.retry_after > p.retry_after_cap_s:
                        raise LLMUnavailableError(
                            f"rate limited, retry-after {exc.retry_after:.0f}s is too long: {exc}"
                        ) from exc
                    delay = max(delay, exc.retry_after)
                if attempt == p.max_attempts:
                    raise LLMUnavailableError(f"gave up after {attempt} attempts: {exc}") from exc
                self._clock.sleep(delay)
        raise AssertionError("unreachable: max_attempts must be at least 1")

    def _pace_and_count(self) -> None:
        p = self._policy
        if p.max_requests is not None and self.requests_made >= p.max_requests:
            raise LLMConfigError(f"request budget of {p.max_requests} exhausted")
        now = self._clock.monotonic()
        if self._last_start is not None and p.min_interval_s > 0:
            wait = p.min_interval_s - (now - self._last_start)
            if wait > 0:
                self._clock.sleep(wait)
                now = self._clock.monotonic()
        self._last_start = now
        self.requests_made += 1
