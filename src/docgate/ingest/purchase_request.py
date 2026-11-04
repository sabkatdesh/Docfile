"""Load the purchase request CSV. File I/O stays here so rules remain pure."""

from __future__ import annotations

import csv
from pathlib import Path

from docgate.domain.models import PRLine
from docgate.domain.money import to_money


def load_pr_lines(path: Path) -> dict[str, PRLine]:
    lines: dict[str, PRLine] = {}
    # utf-8-sig: the sample CSV starts with a BOM that would corrupt the first header.
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            line = PRLine(
                pr_number=row["PR number"].strip(),
                item_code=row["Item"].strip(),
                description=row["Description"].strip(),
                unit=row["Unit"].strip(),
                qty=to_money(row["Quantity requested"].strip()),
                max_unit_price=to_money(row["Maximum unit price (BDT)"].strip()),
            )
            if line.item_code in lines:
                raise ValueError(f"duplicate item code {line.item_code!r} in {path}")
            lines[line.item_code] = line
    return lines
