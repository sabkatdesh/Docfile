from __future__ import annotations

import pytest

from docgate.llm.provider import (
    LLMBadResponseError,
    LLMConfigError,
    LLMRateLimitedError,
    LLMRequest,
    LLMServerError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from docgate.llm.retry import RetryingProvider, RetryPolicy
from tests.fakes import FakeClock, FakeProvider

REQ = LLMRequest(
    system="s", user="u", schema={}, schema_name="n", prompt_version="p", schema_version="v",
    params={},
)  # fmt: skip


def _wrap(
    script: list[str | Exception], policy: RetryPolicy | None = None
) -> tuple[RetryingProvider, FakeProvider, FakeClock]:
    inner, clock = FakeProvider(script), FakeClock()
    return RetryingProvider(inner, clock, policy or RetryPolicy()), inner, clock


def test_success_needs_no_sleep() -> None:
    p, inner, clock = _wrap(["{}"])
    assert p.complete_json(REQ) == "{}"
    assert inner.calls == 1
    assert clock.sleeps == []


def test_429_honours_retry_after_when_longer_than_backoff() -> None:
    p, inner, clock = _wrap([LLMRateLimitedError("slow down", retry_after=5.0), "{}"])
    assert p.complete_json(REQ) == "{}"
    assert clock.sleeps == [5.0]
    assert inner.calls == 2


def test_backoff_doubles_then_succeeds() -> None:
    p, _, clock = _wrap([LLMTimeoutError("t"), LLMServerError("5xx"), LLMTimeoutError("t"), "{}"])
    assert p.complete_json(REQ) == "{}"
    assert clock.sleeps == [2.0, 4.0, 8.0]


def test_gives_up_after_max_attempts_without_crashing_the_caller_type() -> None:
    p, inner, clock = _wrap([LLMTimeoutError("t")] * 4)
    with pytest.raises(LLMUnavailableError, match="4 attempts"):
        p.complete_json(REQ)
    assert inner.calls == 4
    assert clock.sleeps == [2.0, 4.0, 8.0]


def test_backoff_is_capped() -> None:
    policy = RetryPolicy(max_attempts=4, base_delay_s=20.0, max_delay_s=30.0)
    p, _, clock = _wrap([LLMTimeoutError("t")] * 4, policy)
    with pytest.raises(LLMUnavailableError):
        p.complete_json(REQ)
    assert clock.sleeps == [20.0, 30.0, 30.0]


def test_huge_retry_after_fails_fast() -> None:
    p, inner, clock = _wrap([LLMRateLimitedError("daily cap", retry_after=3600.0), "{}"])
    with pytest.raises(LLMUnavailableError, match="retry-after"):
        p.complete_json(REQ)
    assert inner.calls == 1
    assert clock.sleeps == []


@pytest.mark.parametrize("error", [LLMBadResponseError("400"), LLMConfigError("401")])
def test_non_transport_errors_are_not_retried(error: Exception) -> None:
    p, inner, clock = _wrap([error, "{}"])
    with pytest.raises(type(error)):
        p.complete_json(REQ)
    assert inner.calls == 1
    assert clock.sleeps == []


def test_minimum_interval_paces_calls() -> None:
    p, _, clock = _wrap(["a", "b"], RetryPolicy(min_interval_s=25.0))
    p.complete_json(REQ)
    clock.now += 10.0
    p.complete_json(REQ)
    assert clock.sleeps == [15.0]


def test_request_budget_is_a_hard_stop() -> None:
    p, inner, _ = _wrap(["a", "b", "c"], RetryPolicy(max_requests=2))
    p.complete_json(REQ)
    p.complete_json(REQ)
    with pytest.raises(LLMConfigError, match="budget"):
        p.complete_json(REQ)
    assert inner.calls == 2
    assert p.requests_made == 2
