"""The evaluation page's data: golden vs actual, the confusion matrix, unsafe errors.

Pure. The score is only ever computed from the machine decision; a human decision is shown
beside it so a later resolution cannot mask a wrong verdict.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from docgate.domain.models import Decision
from docgate.evaluation.mutations import MutationView
from docgate.evaluation.score import ORDER, EvalResult


class EvalRowView(BaseModel):
    pack: int
    pack_id: str
    expected: Decision | None
    actual: Decision | None
    match: bool
    human_decision: Decision | None


class ConfusionView(BaseModel):
    """`counts[i][j]`: packs expected as `labels[i]` that the system decided as `labels[j]`."""

    labels: list[Decision]
    counts: list[list[int]]


class GoldenView(BaseModel):
    total: int
    correct: int
    passed: bool
    unsafe: list[int]
    conservative_misses: list[int]
    rows: list[EvalRowView]
    confusion: ConfusionView


class EvalView(BaseModel):
    golden: GoldenView
    mutation: MutationView


def build_golden_view(result: EvalResult, human: Mapping[int, Decision | None]) -> GoldenView:
    return GoldenView(
        total=result.total,
        correct=result.correct,
        passed=result.passed,
        unsafe=result.unsafe,
        conservative_misses=result.conservative_misses,
        rows=[
            EvalRowView(
                pack=r.pack,
                pack_id=f"supplier-pack-{r.pack:02d}",
                expected=r.expected,
                actual=r.actual,
                match=r.match,
                human_decision=human.get(r.pack),
            )
            for r in result.rows
        ],
        confusion=ConfusionView(
            labels=list(ORDER),
            counts=[[result.confusion[(e, a)] for a in ORDER] for e in ORDER],
        ),
    )
