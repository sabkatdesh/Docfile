"""Everything the report needs from the PR comparison, computed once.

Display data only: rules recompute what they need and decide with exact comparisons.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from docgate.compare.arithmetic import ArithmeticFinding, check_arithmetic
from docgate.compare.pr import (
    find_pr_line,
    price_comparability_problem,
    price_delta_pct,
    qty_delta_pct,
)
from docgate.domain.config import RuleConfig
from docgate.domain.models import Extraction, PRLine


@dataclass(frozen=True)
class Comparison:
    pr_line: PRLine | None
    price_delta_pct: Decimal | None
    qty_delta_pct: Decimal | None
    price_note: str | None  # why the price could not be compared, when it could not
    arithmetic: list[ArithmeticFinding]


def compare(ex: Extraction, lines: Mapping[str, PRLine], cfg: RuleConfig) -> Comparison:
    pr = find_pr_line(ex, lines)
    return Comparison(
        pr_line=pr,
        price_delta_pct=price_delta_pct(ex, pr),
        qty_delta_pct=qty_delta_pct(ex, pr),
        price_note=price_comparability_problem(ex, pr),
        arithmetic=check_arithmetic(ex, cfg),
    )
