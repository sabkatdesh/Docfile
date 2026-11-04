"""Golden verdicts from SPEC section 9. Do not edit to make tests pass; ask instead."""

from __future__ import annotations

from docgate.domain.models import Decision, RuleStatus

A, R, N = Decision.APPROVE, Decision.REJECT, Decision.NEEDS_PERSON
FAIL, UNKNOWN = RuleStatus.FAIL, RuleStatus.UNKNOWN

GOLDEN: dict[int, Decision] = {
    1: A,
    2: A,
    3: R,
    4: N,
    5: R,
    6: R,
    7: N,
    8: R,
    9: N,
    10: R,
}

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
