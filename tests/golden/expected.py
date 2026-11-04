"""Golden verdicts from SPEC section 9. Do not edit to make tests pass; ask instead."""

from __future__ import annotations

from pathlib import Path

from docgate.domain.models import Decision, RuleStatus
from docgate.evaluation.golden import load_golden

FAIL, UNKNOWN = RuleStatus.FAIL, RuleStatus.UNKNOWN

# Single source of truth, shared with `python tasks.py eval`: data/golden/expected.json.
GOLDEN: dict[int, Decision] = load_golden(
    Path(__file__).parents[2] / "data" / "golden" / "expected.json"
)

# Every rule not listed for a pack must PASS.
EXPECTED_NON_PASS: dict[int, dict[str, RuleStatus]] = {
    1: {},
    2: {},
    3: {"R1": FAIL},
    4: {"H1": FAIL},
    5: {"R2": FAIL},
    6: {"R3": FAIL},
    7: {"H2": FAIL},
    8: {"R4": FAIL},
    9: {"H3": FAIL, "H6": FAIL},
    10: {"R5": FAIL, "H5": FAIL, "R1": UNKNOWN, "H1": UNKNOWN},
}
