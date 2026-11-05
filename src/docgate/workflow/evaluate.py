"""The golden evaluation as a service: run every pack once in memory and score the machine
decisions. Cached because replay is deterministic, so a second run would say the same thing."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from pathlib import Path

from docgate.domain.models import Decision
from docgate.evaluation.score import EvalResult, score
from docgate.workflow.deps import Deps
from docgate.workflow.graph import build_graph
from docgate.workflow.runner import pack_number, run_packs


class EvalService:
    def __init__(self, deps: Deps, packs: Mapping[str, Path], golden: Mapping[int, Decision]):
        self._deps = deps
        self._packs = dict(packs)
        self._golden = dict(golden)
        self._lock = threading.Lock()
        self._cached: EvalResult | None = None

    def result(self) -> EvalResult:
        with self._lock:
            if self._cached is None:
                states = run_packs(build_graph(self._deps), list(self._packs.values()))
                actual = {pack_number(s["pack_id"]): s["verdict"].decision for s in states}
                self._cached = score(self._golden, actual)
            return self._cached
