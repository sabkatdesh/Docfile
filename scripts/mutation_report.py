"""Run the mutation suite and write its results for the API (`GET /api/eval`).

Uses the same mutations and the same real pipeline as `tests/mutation`; it only records what each
one did instead of asserting. Writing the file is the only side effect. A test regenerates the
results and compares them with the committed file, so the file cannot go stale unnoticed.
"""

from __future__ import annotations

import sys
from pathlib import Path

from tests.mutation.harness import Mutation, non_pass, run_mutant
from tests.mutation.test_mutations import CONTROLS, MUTATIONS, TWINS, WHITESPACE_PROBES

from docgate.domain.models import Decision
from docgate.evaluation.mutations import (
    DEFAULT_FILE,
    MutationCase,
    MutationResults,
    render_results,
)

ROOT = Path(__file__).resolve().parents[1]


def _case(m: Mutation, family: str, *, expect: Decision, stale: bool = False) -> MutationCase:
    state = run_mutant(m, stale=stale)
    actual = state["verdict"].decision
    fired = non_pass(state)
    if family in {"control", "whitespace"}:
        ok = actual is expect and not fired
    elif family == "stale":
        ok = actual is expect  # the recorded extraction no longer matches the text
    else:
        ok = actual is expect and fired == dict(m.fired)
    return MutationCase(
        id=m.id,
        family=family,
        expect=expect,
        actual=actual,
        fired=fired,
        ok=ok and not state["errors"],
    )


def build_results() -> MutationResults:
    cases = [_case(m, "mutation", expect=m.expect) for m in MUTATIONS]
    cases += [_case(m, "twin", expect=m.expect) for m in TWINS]
    cases += [_case(m, "control", expect=Decision.APPROVE) for m in CONTROLS]
    cases += [_case(m, "whitespace", expect=Decision.APPROVE) for m in WHITESPACE_PROBES]
    cases += [_case(m, "stale", expect=Decision.NEEDS_PERSON, stale=True) for m in MUTATIONS]
    return MutationResults(cases=cases)


def main() -> int:
    results = build_results()
    path = ROOT / DEFAULT_FILE
    path.write_text(render_results(results), encoding="utf-8", newline="")
    failed = [c.id for c in results.cases if not c.ok]
    print(f"{len(results.cases) - len(failed)}/{len(results.cases)} cases ok; wrote {path}")
    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
