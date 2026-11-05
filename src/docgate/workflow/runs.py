"""Background runs for the API: one run at a time, an ordered event log per run, and one active
checkpoint database. HTTP-free, so the lifecycle is testable without a server.

The graph, the rules and the review store are the existing ones; this module only schedules them
and records what happened. It never decides anything.
"""

from __future__ import annotations

import datetime
import logging
import secrets
import sqlite3
import threading
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docgate.domain.config import DEFAULT_CONFIG
from docgate.domain.models import Decision
from docgate.reporting.writer import write_run
from docgate.review.checkpoint import sqlite_saver
from docgate.review.fresh import discard
from docgate.review.payload import QUESTION
from docgate.review.service import Clock, GraphReviewStore, utc_now
from docgate.review.store import PendingReview, ReviewError
from docgate.workflow.deps import Deps
from docgate.workflow.detail import build_list_item
from docgate.workflow.graph import build_graph
from docgate.workflow.progress import Finished, NodeDone, Paused, stream_pack
from docgate.workflow.runner import OperatorError, pack_number, report_of
from docgate.workflow.state import PackState

log = logging.getLogger(__name__)

# The nodes a pack passes through. `escalate` is added only when a step fails.
STEPS = [
    "ingest",
    "extract_llm",
    "extract_regex",
    "reconcile",
    "compare_pr",
    "apply_rules",
    "decide",
    "human_gate",
    "report",
]


class RunError(Exception):
    """A run request that cannot be honoured. Nothing was started or changed."""


class RunInProgressError(RunError):
    def __init__(self, run_id: str) -> None:
        super().__init__(f"run {run_id} is still in progress; wait for it to finish")
        self.run_id = run_id


class PendingReviewsError(RunError):
    def __init__(self, pack_ids: Sequence[str]) -> None:
        self.pack_ids = list(pack_ids)
        super().__init__(
            f"starting a fresh run would discard {len(self.pack_ids)} review(s) still waiting "
            f"for a decision ({', '.join(self.pack_ids)}). Resolve them, resume the record, or "
            "discard them explicitly."
        )


class UnknownPackNumberError(RunError):
    pass


class UnknownRunError(RunError):
    pass


@dataclass(frozen=True)
class RunEvent:
    seq: int
    type: str
    data: dict[str, Any]
    ts: str


@dataclass(frozen=True)
class RunInfo:
    run_id: str
    packs: list[str]
    resume: bool


@dataclass
class _Run:
    info: RunInfo
    events: list[RunEvent] = field(default_factory=list)
    finished: bool = False


def _now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="milliseconds")


class RunManager:
    def __init__(
        self,
        deps: Deps,
        packs: Mapping[str, Path],
        db: Path,
        *,
        out_dir: Path | None = None,
        step_delay_s: float = 0.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Clock = utc_now,
    ) -> None:
        self._deps = deps
        self._packs = dict(sorted(packs.items()))
        self._db = db
        self.out_dir = out_dir
        self._step_delay_s = step_delay_s
        self._sleep = sleep
        self._clock = clock
        self._lock = threading.RLock()  # guards the database handle and the active-run slot
        self._changed = threading.Condition()  # wakes event readers
        self._runs: dict[str, _Run] = {}
        self._active: str | None = None
        self._thread: threading.Thread | None = None
        self._stack = ExitStack()
        self._store: GraphReviewStore
        self._graph: Any
        self._open()

    # -- database lifecycle ---------------------------------------------------------------

    def _open(self) -> None:
        stack = ExitStack()
        try:
            saver = stack.enter_context(sqlite_saver(self._db))
            graph = build_graph(self._deps, checkpointer=saver)
            store = GraphReviewStore(graph, saver, self._clock)
            store.pack_ids()  # fails here, not in the middle of a request, on a corrupt file
        except sqlite3.DatabaseError as exc:
            stack.close()
            raise ReviewError(
                f"{self._db} is not a readable checkpoint database ({exc}); delete it"
            ) from exc
        except BaseException:
            stack.close()
            raise
        self._stack, self._graph, self._store = stack, graph, store

    def close(self, wait_s: float = 30.0) -> None:
        """Let an active run finish (closing the database under it would corrupt its last step),
        then release the file."""
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(wait_s)  # not under the lock: the run takes it when it finishes
        with self._lock:
            self._stack.close()

    def _reset(self) -> None:
        self._stack.close()  # an open handle locks the file on Windows
        discard(self._db)
        self._open()

    # -- what the API reads ---------------------------------------------------------------

    @property
    def pack_ids(self) -> list[str]:
        return list(self._packs)

    def pack_path(self, pack_id: str) -> Path | None:
        """The PDF of a listed pack. The only way a pack id becomes a path: an allowlist lookup."""
        return self._packs.get(pack_id)

    def has_run(self, run_id: str) -> bool:
        return run_id in self._runs

    @property
    def active_run_id(self) -> str | None:
        return self._active

    def state(self, pack_id: str) -> PackState | None:
        with self._lock:
            return self._store.state(pack_id)

    def states(self) -> list[PackState]:
        with self._lock:
            return self._store.states()

    def pending(self) -> list[PendingReview]:
        with self._lock:
            return self._store.pending()

    def resolve(self, pack_id: str, decision: Decision, reason: str, reviewer: str) -> PackState:
        with self._lock:
            if self._active is not None:
                raise RunInProgressError(self._active)
            final = self._store.resolve(pack_id, decision, reason, reviewer)
            self._write_reports()
            return final

    # -- starting a run -------------------------------------------------------------------

    def _select(self, numbers: Sequence[int] | None) -> list[str]:
        if numbers is None:
            return list(self._packs)
        by_number = {pack_number(p): p for p in self._packs}
        missing = sorted(set(numbers) - set(by_number))
        if missing:
            known = ", ".join(str(n) for n in sorted(by_number))
            raise UnknownPackNumberError(
                f"no pack numbered {', '.join(map(str, missing))} (known: {known})"
            )
        return [by_number[n] for n in sorted(set(numbers))]

    def start(
        self,
        numbers: Sequence[int] | None,
        *,
        resume: bool = False,
        discard_pending: bool = False,
    ) -> RunInfo:
        with self._lock:
            if self._active is not None:
                raise RunInProgressError(self._active)
            selected = self._select(numbers)
            if not resume:
                waiting = [p.pack_id for p in self._store.pending()]
                if waiting and not discard_pending:
                    raise PendingReviewsError(waiting)
                if self._store.pack_ids():
                    self._reset()
            info = RunInfo(secrets.token_hex(6), selected, resume)
            run = _Run(info)
            self._runs[info.run_id] = run
            self._active = info.run_id
            self._thread = threading.Thread(
                target=self._execute, args=(run,), name=f"run-{info.run_id}"
            )
            self._thread.start()
        return info

    # -- the background run ---------------------------------------------------------------

    def _emit(self, run: _Run, type_: str, **data: Any) -> None:
        with self._changed:
            payload = {"run_id": run.info.run_id, **data}
            run.events.append(RunEvent(len(run.events) + 1, type_, payload, _now()))
            self._changed.notify_all()

    def _execute(self, run: _Run) -> None:
        info = run.info
        status = "completed"
        outcome: dict[str, PackState] = {}
        skipped: list[str] = []
        try:
            self._emit(
                run, "run_started", packs=info.packs, total=len(info.packs), resume=info.resume
            )
            on_record = set(self._store.pack_ids()) if info.resume else set()
            for index, pack_id in enumerate(info.packs, start=1):
                if pack_id in on_record:  # re-running would silently restart a paused pack
                    skipped.append(pack_id)
                    self._emit(run, "pack_skipped", pack_id=pack_id, reason="already on record")
                    continue
                self._emit(
                    run,
                    "pack_started",
                    pack_id=pack_id,
                    index=index,
                    total=len(info.packs),
                    steps=STEPS,
                )
                outcome[pack_id] = self._run_pack(run, pack_id)
        except OperatorError as exc:
            status = "failed"
            self._emit(run, "error", message=str(exc), pack_id=None, fatal=True)
        except Exception as exc:  # a crash must end the stream cleanly, never hang the client
            log.exception("run %s crashed", info.run_id)
            status = "failed"
            self._emit(
                run, "error", message=f"{type(exc).__name__}: {exc}", pack_id=None, fatal=True
            )
        finally:
            self._finish(run, status, outcome, skipped)

    def _run_pack(self, run: _Run, pack_id: str) -> PackState:
        state: PackState = {}
        for progress in stream_pack(self._graph, pack_id, self._packs[pack_id]):
            if isinstance(progress, NodeDone):
                self._emit(
                    run,
                    "node_completed",
                    pack_id=pack_id,
                    node=progress.node,
                    ok=progress.ok,
                    elapsed_ms=progress.elapsed_ms,
                    message=progress.message,
                )
                if self._step_delay_s:  # lets a demo be watched at human speed
                    self._sleep(self._step_delay_s)
            elif isinstance(progress, Paused):
                state = progress.state
                self._emit(
                    run,
                    "pack_paused",
                    pack_id=pack_id,
                    machine_decision=state["verdict"].decision.value,
                    reason=state["verdict"].reason,
                    question=QUESTION,
                )
            elif isinstance(progress, Finished):
                state = progress.state
                item = build_list_item(pack_id, self._packs[pack_id].name, state)
                self._emit(
                    run,
                    "pack_finished",
                    pack_id=pack_id,
                    decision=item.decision.value if item.decision else None,
                    headline=item.headline,
                    primary_rule=item.primary_rule,
                )
        config_errors = [e for e in state.get("errors", []) if e.kind == "config"]
        if config_errors:  # escalating every pack would hide a bad key or an exhausted budget
            raise OperatorError("; ".join(f"{e.node}: {e.message}" for e in config_errors))
        return state

    def _finish(
        self, run: _Run, status: str, outcome: dict[str, PackState], skipped: list[str]
    ) -> None:
        paused = [p for p, s in outcome.items() if "report" not in s and "verdict" in s]
        counts = Counter(s["verdict"].decision.value for s in outcome.values() if "verdict" in s)
        self._emit(
            run,
            "run_finished",
            status=status,
            counts=dict(counts),
            paused=paused,
            finished=[p for p in outcome if p not in paused],
            skipped=skipped,
        )
        with self._lock:
            run.finished = True
            self._active = None
            self._write_reports()
        with self._changed:
            self._changed.notify_all()

    def _write_reports(self) -> None:
        """Audit files for every pack on record, as the CLI writes them."""
        if self.out_dir is None:
            return
        try:
            write_run([report_of(s, DEFAULT_CONFIG) for s in self._store.states()], self.out_dir)
        except OSError:
            log.warning("could not write reports to %s", self.out_dir, exc_info=True)

    # -- reading the event log ------------------------------------------------------------

    def events_after(self, run_id: str, after: int, timeout: float) -> tuple[list[RunEvent], bool]:
        """Events with seq > `after`, waiting up to `timeout` for the first one. The flag says
        the run is over and nothing more will come."""
        run = self._runs.get(run_id)
        if run is None:
            raise UnknownRunError(f"unknown run {run_id!r}")
        with self._changed:
            if len(run.events) <= after and not self._is_over(run):
                self._changed.wait(timeout)
            new = run.events[after:]
            return new, self._is_over(run) and len(run.events) <= after + len(new)

    @staticmethod
    def _is_over(run: _Run) -> bool:
        return run.finished and bool(run.events) and run.events[-1].type == "run_finished"
