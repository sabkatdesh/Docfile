"""Test doubles for the LLM layer. No network, no real time."""

from __future__ import annotations

from collections.abc import Iterable

from docgate.llm.provider import LLMRequest


class FakeClock:
    """Records sleeps and advances only when asked, so backoff tests run instantly."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def monotonic(self) -> float:
        return self.now


class FakeProvider:
    """Plays back scripted responses; an Exception in the script is raised."""

    def __init__(self, script: Iterable[str | Exception], model_id: str = "fake-model") -> None:
        self.model_id = model_id
        self._script = list(script)
        self.requests: list[LLMRequest] = []

    @property
    def calls(self) -> int:
        return len(self.requests)

    def complete_json(self, request: LLMRequest) -> str:
        self.requests.append(request)
        if not self._script:
            raise AssertionError("FakeProvider script exhausted")
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
