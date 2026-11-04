"""Expected values are written by hand from the PDFs in data/sample/."""

from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from docgate.domain.models import DayRange
from docgate.extraction.base import Outcome
from docgate.extraction.quotes import raw_in_quote, verify_quote
from docgate.extraction.regex import RegexExtractor
from docgate.ingest.pdf import extract_text

D = Decimal
SAMPLE = Path(__file__).parents[2] / "data" / "sample"
Totals = tuple[str, str, str] | None


def _row(
    supplier: str,
    qno: str,
    date: str,
    item: str,
    desc: str,
    qty: str,
    unit: str,
    price: str,
    totals: Totals,
    tin: tuple[str, str] | None,
    adv: str,
    pay: tuple[int, int],
    deliv: int,
    pen: str | None,
    valid: int,
) -> dict[str, Any]:
    """None in the result means the extractor must say ABSENT."""
    return {
        "supplier": supplier,
        "quotation_no": qno,
        "date": datetime.date.fromisoformat(date),
        "item_code": item,
        "description": desc,
        "qty": D(qty),
        "unit": unit,
        "unit_price": D(price),
        "subtotal": D(totals[0]) if totals else None,
        "vat_amount": D(totals[1]) if totals else None,
        "total": D(totals[2]) if totals else D("282000.00"),
        "vat_shown_separately": totals is not None,
        "tin": tin[0] if tin else None,
        "bin": tin[1] if tin else None,
        "advance_pct": D(adv),
        "payment_days": DayRange(min=pay[0], max=pay[1]),
        "delivery_days": deliv,
        "penalty_pct_per_week": D(pen) if pen else None,
        "validity_days": valid,
    }


FAB = "Cotton twill fabric, 280 gsm"
ZIP = "Metal zipper, 18 cm"
THR = "Polyester sewing thread, cone"
BAG = "Poly bag, 30 x 40 cm"
BOX = "Carton box, 5-ply"

EXPECTED: dict[int, dict[str, Any]] = {
    1: _row(
        "Padma Textile Mills Ltd",
        "QT-2026-901",
        "2026-10-21",
        "A",
        FAB,
        "12000",
        "metre",
        "472.00",
        ("5664000.00", "849600.00", "6513600.00"),
        ("101458013391", "000170141-0101"),
        "10",
        (45, 45),
        24,
        "1",
        45,
    ),
    2: _row(
        "Jamuna Trims and Accessories",
        "QT-2026-902",
        "2026-10-22",
        "B",
        ZIP,
        "20000",
        "piece",
        "36.00",
        ("720000.00", "108000.00", "828000.00"),
        ("102458023391", "000270241-0101"),
        "0",
        (30, 30),
        21,
        "0.75",
        30,
    ),
    3: _row(
        "Karnaphuli Yarn Traders",
        "QT-2026-903",
        "2026-10-23",
        "C",
        THR,
        "800",
        "cone",
        "229.00",
        ("183200.00", "27480.00", "210680.00"),
        ("103458033391", "000370341-0101"),
        "15",
        (40, 40),
        20,
        "0.5",
        30,
    ),
    4: _row(
        "Surma Packaging Industries",
        "QT-2026-904",
        "2026-10-24",
        "D",
        BAG,
        "50000",
        "piece",
        "6.65",
        ("332500.00", "49875.00", "382375.00"),
        ("104458043391", "000470441-0101"),
        "10",
        (30, 30),
        28,
        "0.6",
        40,
    ),
    5: _row(
        "Meghna Carton Works",
        "QT-2026-905",
        "2026-10-25",
        "E",
        BOX,
        "3000",
        "piece",
        "92.00",
        ("276000.00", "41400.00", "317400.00"),
        ("105458053391", "000570541-0101"),
        "40",
        (30, 30),
        25,
        "1",
        30,
    ),
    6: _row(
        "Teesta Fabrics Ltd",
        "QT-2026-906",
        "2026-10-26",
        "A",
        FAB,
        "12000",
        "metre",
        "465.00",
        ("5580000.00", "837000.00", "6417000.00"),
        ("106458063391", "000670641-0101"),
        "10",
        (60, 60),
        27,
        None,
        30,
    ),
    7: _row(
        "Rupsha Zipper Factory",
        "QT-2026-907",
        "2026-10-20",
        "B",
        ZIP,
        "16500",
        "piece",
        "35.00",
        ("577500.00", "86625.00", "664125.00"),
        ("107458073391", "000770741-0101"),
        "0",
        (45, 45),
        22,
        "0.5",
        35,
    ),
    8: _row(
        "Bhairab Thread and Co",
        "QT-2026-908",
        "2026-10-21",
        "C",
        THR,
        "800",
        "cone",
        "205.00",
        ("164000.00", "24600.00", "188600.00"),
        None,
        "10",
        (30, 30),
        18,
        "0.5",
        30,
    ),
    9: _row(
        "Dhaleshwari Poly Pack",
        "QT-2026-909",
        "2026-10-22",
        "D",
        BAG,
        "50000",
        "piece",
        "6.40",
        ("322000.00", "48300.00", "370300.00"),
        ("109458093391", "000970941-0101"),
        "5",
        (30, 90),
        28,
        "0.5",
        30,
    ),
    10: _row(
        "Kushiyara Box Industries",
        "QT-2026-910",
        "2026-10-23",
        "E",
        BOX,
        "3000",
        "piece",
        "94.00",
        None,
        ("110458103391", "001071041-0101"),
        "10",
        (45, 45),
        60,
        "0.5",
        30,
    ),
}


def _text(n: int) -> str:
    return extract_text(SAMPLE / f"supplier-pack-{n:02d}.pdf")


@pytest.mark.parametrize("n", sorted(EXPECTED))
def test_regex_extracts_the_expected_values(n: int) -> None:
    out = RegexExtractor().extract(_text(n))
    assert out.failure is None
    for name, want in EXPECTED[n].items():
        cand = out.candidates[name]
        if want is None:
            assert cand.outcome is Outcome.ABSENT, f"pack {n} {name}: {cand}"
        else:
            assert cand.outcome is Outcome.FOUND, f"pack {n} {name}: {cand}"
            assert cand.value == want, f"pack {n} {name}"
            assert type(cand.value) is type(want), f"pack {n} {name}"


@pytest.mark.parametrize("n", sorted(EXPECTED))
def test_every_regex_quote_is_in_the_text_and_holds_the_raw_value(n: int) -> None:
    text = _text(n)
    for name, cand in RegexExtractor().extract(text).candidates.items():
        if cand.outcome is Outcome.FOUND:
            assert verify_quote(cand.quote, text), f"pack {n} {name}: {cand.quote!r}"
            if cand.raw is not None:
                assert raw_in_quote(cand.raw, cand.quote or ""), f"pack {n} {name}"


def test_pack05_duplicated_advance_sentence_is_one_value() -> None:
    cand = RegexExtractor().extract(_text(5)).candidates["advance_pct"]
    assert cand.outcome is Outcome.FOUND
    assert cand.value == D("40")


def test_pack05_payment_days_come_from_the_balance_clause() -> None:
    cand = RegexExtractor().extract(_text(5)).candidates["payment_days"]
    assert cand.value == DayRange(min=30, max=30)
    assert "60%" in (cand.quote or "")


def test_pack09_weeks_and_range_keep_their_printed_form() -> None:
    c = RegexExtractor().extract(_text(9)).candidates
    assert c["delivery_days"].raw == "4 weeks"
    assert c["delivery_days"].value == 28
    assert c["payment_days"].raw == "30 to 90 days"


def test_pack09_arithmetic_error_is_reported_not_repaired() -> None:
    assert RegexExtractor().extract(_text(9)).candidates["subtotal"].value == D("322000.00")


def test_pack08_has_no_tin_or_bin_and_pack06_no_penalty() -> None:
    c8 = RegexExtractor().extract(_text(8)).candidates
    assert c8["tin"].outcome is Outcome.ABSENT
    assert c8["bin"].outcome is Outcome.ABSENT
    c6 = RegexExtractor().extract(_text(6)).candidates
    assert c6["penalty_pct_per_week"].outcome is Outcome.ABSENT


def test_pack10_vat_flag_false_is_quoted_from_the_tax_inclusive_total() -> None:
    cand = RegexExtractor().extract(_text(10)).candidates["vat_shown_separately"]
    assert cand.value is False
    assert "all taxes included" in (cand.quote or "")


def test_two_different_advances_are_unreadable_not_guessed() -> None:
    text = _text(1).replace("Balance payable", "20% advance later. Balance payable")
    cand = RegexExtractor().extract(text).candidates["advance_pct"]
    assert cand.outcome is Outcome.UNREADABLE


def test_a_non_template_document_yields_no_guesses() -> None:
    out = RegexExtractor().extract("Hello, this is not a quotation at all.")
    assert not any(c.outcome is Outcome.FOUND for c in out.candidates.values())
