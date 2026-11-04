"""Score actual verdicts against the golden set. Pure: no I/O, no pipeline imports."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

from docgate.domain.models import Decision

ORDER = (Decision.APPROVE, Decision.REJECT, Decision.NEEDS_PERSON)


@dataclass(frozen=True)
class EvalRow:
    pack: int
    expected: Decision | None
    actual: Decision | None

    @property
    def match(self) -> bool:
        return self.expected is not None and self.expected is self.actual


@dataclass(frozen=True)
class EvalResult:
    rows: list[EvalRow]
    confusion: Counter[tuple[Decision, Decision]]
    # Unsafe means a wrong Approve: the costliest error. Nothing else counts.
    unsafe: list[int]
    # Asked a person where the golden says Reject: safe, but not what was expected.
    conservative_misses: list[int]

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def correct(self) -> int:
        return sum(row.match for row in self.rows)

    @property
    def passed(self) -> bool:
        return self.correct == self.total and not self.unsafe


def score(expected: Mapping[int, Decision], actual: Mapping[int, Decision]) -> EvalResult:
    # Union of both sides, so a pack the pipeline skipped or invented is a mismatch.
    packs = sorted(set(expected) | set(actual))
    rows = [EvalRow(n, expected.get(n), actual.get(n)) for n in packs]
    confusion: Counter[tuple[Decision, Decision]] = Counter()
    for row in rows:
        if row.expected is not None and row.actual is not None:
            confusion[(row.expected, row.actual)] += 1
    unsafe = [r.pack for r in rows if r.actual is Decision.APPROVE and not r.match]
    conservative = [
        r.pack for r in rows if r.expected is Decision.REJECT and r.actual is Decision.NEEDS_PERSON
    ]
    return EvalResult(rows, confusion, unsafe, conservative)


def _label(decision: Decision | None) -> str:
    return decision.value if decision else "(none)"


def render_report(result: EvalResult) -> str:
    lines = [f"{'pack':<6}{'expected':<26}{'actual':<26}match"]
    for row in result.rows:
        mark = "ok" if row.match else "MISMATCH"
        lines.append(f"{row.pack:02d}    {_label(row.expected):<26}{_label(row.actual):<26}{mark}")
    lines += [
        "",
        f"accuracy: {result.correct}/{result.total}",
        f"unsafe errors: {len(result.unsafe)}"
        + (f" (packs {', '.join(map(str, result.unsafe))})" if result.unsafe else ""),
        f"conservative misses (Reject expected, person asked): {len(result.conservative_misses)}",
        "",
        "confusion matrix (rows = expected, cols = actual)",
        f"{'':<26}" + "".join(f"{d.value:<26}" for d in ORDER),
    ]
    for exp in ORDER:
        cells = "".join(f"{result.confusion[(exp, act)]:<26}" for act in ORDER)
        lines.append(f"{exp.value:<26}{cells}")
    return "\n".join(lines)


def result_to_dict(result: EvalResult) -> dict[str, object]:
    return {
        "total": result.total,
        "correct": result.correct,
        "unsafe": result.unsafe,
        "conservative_misses": result.conservative_misses,
        "passed": result.passed,
        "rows": [
            {
                "pack": r.pack,
                "expected": r.expected.value if r.expected else None,
                "actual": r.actual.value if r.actual else None,
                "match": r.match,
            }
            for r in result.rows
        ],
        "confusion": {
            f"{exp.value} -> {act.value}": n for (exp, act), n in sorted(result.confusion.items())
        },
    }
