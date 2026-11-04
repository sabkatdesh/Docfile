from decimal import Decimal
from pathlib import Path

import pytest

from docgate.ingest.purchase_request import load_pr_lines

SAMPLE = Path(__file__).parents[2] / "data" / "sample" / "purchase-request.csv"


def test_load_pr_lines_sample() -> None:
    lines = load_pr_lines(SAMPLE)
    assert len(lines) == 5
    assert lines["D"].max_unit_price == Decimal("6.50")
    assert lines["A"].qty == Decimal("12000")
    assert lines["B"].unit == "piece"
    assert lines["A"].pr_number == "PR-2026-114"


def test_duplicate_item_code_raises(tmp_path: Path) -> None:
    p = tmp_path / "pr.csv"
    p.write_text(
        "PR number,Item,Description,Unit,Quantity requested,Maximum unit price (BDT)\n"
        "PR-1,A,x,piece,1,1.00\nPR-1,A,y,piece,2,2.00\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_pr_lines(p)
