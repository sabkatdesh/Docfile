"""The provider switch. Choosing Groq, replay or recording is configuration, not code."""

from __future__ import annotations

from dataclasses import dataclass

from docgate.extraction.llm import LLMExtractor
from docgate.extraction.prompt import load_prompt
from docgate.llm.groq import GroqProvider, make_client
from docgate.llm.provider import LLMProvider
from docgate.llm.replay_provider import RecordingProvider, ReplayProvider
from docgate.llm.retry import Clock, RetryingProvider, RetryPolicy, SystemClock
from docgate.settings import Settings, request_params


@dataclass(frozen=True)
class LLMStack:
    extractor: LLMExtractor
    # Present only when live: lets the caller report spend and drop failed recordings.
    live: RetryingProvider | None = None
    recorder: RecordingProvider | None = None


def _live_provider(settings: Settings, clock: Clock) -> RetryingProvider:
    key = settings.require_api_key()  # fails before any network call
    groq_provider = GroqProvider(make_client(key), settings.groq_model, settings.timeout_s)
    policy = RetryPolicy(min_interval_s=settings.min_interval_s, max_requests=settings.max_requests)
    return RetryingProvider(groq_provider, clock, policy)


def build_llm_stack(
    settings: Settings,
    *,
    record: bool = False,
    overwrite: bool = False,
    clock: Clock | None = None,
) -> LLMStack:
    clock = clock or SystemClock()
    provider: LLMProvider
    live: RetryingProvider | None = None
    recorder: RecordingProvider | None = None
    if record:
        live = _live_provider(settings, clock)
        recorder = RecordingProvider(live, settings.recorded_dir, overwrite=overwrite)
        provider = recorder
    elif settings.provider == "groq":
        live = _live_provider(settings, clock)
        provider = live
    else:
        provider = ReplayProvider(settings.recorded_dir, settings.groq_model)
    extractor = LLMExtractor(provider, load_prompt(), request_params(settings))
    return LLMStack(extractor, live, recorder)
