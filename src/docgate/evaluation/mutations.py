"""Mutation-suite results as data. The suite itself lives in `tests/`; `scripts/mutation_report.py`
runs it and writes this file, and the API only reads it, so a request never runs the suite."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from docgate.domain.models import Decision, RuleStatus

SCHEMA_VERSION = 1
FAMILY_ORDER = ("mutation", "twin", "control", "whitespace", "stale")
DEFAULT_FILE = Path("data/golden/mutation_results.json")
HINT = "run `python tasks.py mutation-report` to generate it"


class MutationCase(BaseModel):
    id: str
    family: str
    expect: Decision
    actual: Decision
    fired: dict[str, RuleStatus]  # the rules that were not PASS
    ok: bool


class MutationResults(BaseModel):
    schema_version: int = SCHEMA_VERSION
    cases: list[MutationCase]


def render_results(results: MutationResults) -> str:
    # No timestamps, so a rerun is byte-identical and the committed file can be compared.
    return results.model_dump_json(indent=2) + "\n"


class MutationGroup(BaseModel):
    family: str
    total: int
    passed: int
    cases: list[MutationCase]


class MutationView(BaseModel):
    available: bool
    reason: str | None
    total: int
    passed: int
    groups: list[MutationGroup]


def _unavailable(reason: str) -> MutationView:
    return MutationView(available=False, reason=reason, total=0, passed=0, groups=[])


def _family_rank(family: str) -> int:
    return FAMILY_ORDER.index(family) if family in FAMILY_ORDER else len(FAMILY_ORDER)


def _group(family: str, cases: list[MutationCase]) -> MutationGroup:
    return MutationGroup(
        family=family, total=len(cases), passed=sum(c.ok for c in cases), cases=cases
    )


def mutation_view(path: Path) -> MutationView:
    """What the API reports. A missing or unreadable file is said so, never replaced by numbers."""
    try:
        results = MutationResults.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return _unavailable(f"{path} does not exist; {HINT}")
    except (OSError, ValueError, ValidationError) as exc:
        return _unavailable(f"{path} could not be read ({type(exc).__name__}); {HINT}")
    families = sorted({c.family for c in results.cases}, key=_family_rank)
    return MutationView(
        available=True,
        reason=None,
        total=len(results.cases),
        passed=sum(c.ok for c in results.cases),
        groups=[_group(f, [c for c in results.cases if c.family == f]) for f in families],
    )
