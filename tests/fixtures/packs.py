"""Hand-written extractions for the 10 sample packs, with quotes copied from the PDF text.

These stand in for the real extractors until M2. Every OK field carries a verbatim quote
(checked against the PDF text by the golden tests).
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from docgate.domain.models import DayRange, Extraction, Field
from tests.factories import absent, ok

D = Decimal
_ADV = " advance payable with the purchase order"
_NO_ADV = "No advance payment required"


def _pack(
    *,
    supplier: str,
    qno: str,
    date: str,
    item: str,
    desc: str,
    qty: tuple[str, str],  # (value, text as printed)
    unit: str,
    price: str,
    amount: str,
    totals: tuple[str, str, str] | None,  # subtotal, vat, total as printed; None = VAT-inclusive
    tin: tuple[str, str] | None,
    adv: tuple[str, str],
    pay: tuple[int, int, str],
    deliv: tuple[int, str],
    pen: tuple[str, str] | None,
    valid: tuple[int, str],
) -> Extraction:
    row = f"{item} {desc} {qty[1]} {unit} {price} {amount}"
    fields: dict[str, Field[Any]] = {
        "supplier": ok(supplier, supplier),
        "quotation_no": ok(qno, f"Quotation no. {qno}"),
        "date": ok(datetime.date.fromisoformat(date), f"Date {date}"),
        "item_code": ok(item, row),
        "description": ok(desc, row),
        "qty": ok(D(qty[0]), row),
        "unit": ok(unit, row),
        "unit_price": ok(D(price), row),
        "advance_pct": ok(D(adv[0]), adv[1]),
        "payment_days": ok(DayRange(min=pay[0], max=pay[1]), pay[2]),
        "delivery_days": ok(deliv[0], deliv[1]),
        "validity_days": ok(valid[0], valid[1]),
        "penalty_pct_per_week": ok(D(pen[0]), pen[1]) if pen else absent(),
    }
    if totals is None:
        total_line = f"Total (all taxes included) {amount}"
        fields["vat_shown_separately"] = ok(False, total_line)
        fields["total"] = ok(D(amount.replace(",", "")), total_line)
    else:
        sub, vat, tot = totals
        fields["vat_shown_separately"] = ok(True, f"VAT 15% {vat}")
        fields["subtotal"] = ok(D(sub.replace(",", "")), f"Subtotal {sub}")
        fields["vat_amount"] = ok(D(vat.replace(",", "")), f"VAT 15% {vat}")
        fields["total"] = ok(D(tot.replace(",", "")), f"Total {tot}")
    if tin:
        fields["tin"] = ok(tin[0], f"TIN: {tin[0]}")
        fields["bin"] = ok(tin[1], f"BIN: {tin[1]}")
    return Extraction(**fields)


PACKS: dict[int, Extraction] = {
    1: _pack(
        supplier="Padma Textile Mills Ltd",
        qno="QT-2026-901",
        date="2026-10-21",
        item="A",
        desc="Cotton twill fabric, 280 gsm",
        qty=("12000", "12,000"),
        unit="metre",
        price="472.00",
        amount="5,664,000.00",
        totals=("5,664,000.00", "849,600.00", "6,513,600.00"),
        tin=("101458013391", "000170141-0101"),
        adv=("10", "10%" + _ADV),
        pay=(45, 45, "Balance payable within 45 days after delivery and acceptance of goods"),
        deliv=(24, "Delivery within 24 days of receiving the purchase order"),
        pen=("1", "Late delivery penalty: 1% of order value for each full week of delay"),
        valid=(45, "valid for 45 days from the date above"),
    ),
    2: _pack(
        supplier="Jamuna Trims and Accessories",
        qno="QT-2026-902",
        date="2026-10-22",
        item="B",
        desc="Metal zipper, 18 cm",
        qty=("20000", "20,000"),
        unit="piece",
        price="36.00",
        amount="720,000.00",
        totals=("720,000.00", "108,000.00", "828,000.00"),
        tin=("102458023391", "000270241-0101"),
        adv=("0", _NO_ADV),
        pay=(30, 30, "Full payment within 30 days of delivery"),
        deliv=(21, "within 21 days from the date of PO"),
        pen=("0.75", "0.75% of the order value per week of delay"),
        valid=(30, "valid for 30 days from the date above"),
    ),
    3: _pack(
        supplier="Karnaphuli Yarn Traders",
        qno="QT-2026-903",
        date="2026-10-23",
        item="C",
        desc="Polyester sewing thread, cone",
        qty=("800", "800"),
        unit="cone",
        price="229.00",
        amount="183,200.00",
        totals=("183,200.00", "27,480.00", "210,680.00"),
        tin=("103458033391", "000370341-0101"),
        adv=("15", "15%" + _ADV),
        pay=(40, 40, "Balance within 40 days of delivery"),
        deliv=(20, "Delivery within 20 days of PO"),
        pen=("0.5", "penalty of 0.5% of order value per week"),
        valid=(30, "valid for 30 days from the date above"),
    ),
    4: _pack(
        supplier="Surma Packaging Industries",
        qno="QT-2026-904",
        date="2026-10-24",
        item="D",
        desc="Poly bag, 30 x 40 cm",
        qty=("50000", "50,000"),
        unit="piece",
        price="6.65",
        amount="332,500.00",
        totals=("332,500.00", "49,875.00", "382,375.00"),
        tin=("104458043391", "000470441-0101"),
        adv=("10", "10%" + _ADV),
        pay=(30, 30, "Payment within 30 days after delivery"),
        deliv=(28, "Delivery within 28 days of PO"),
        pen=("0.6", "penalty of 0.6% of order value per week"),
        valid=(40, "valid for 40 days from the date above"),
    ),
    5: _pack(
        supplier="Meghna Carton Works",
        qno="QT-2026-905",
        date="2026-10-25",
        item="E",
        desc="Carton box, 5-ply",
        qty=("3000", "3,000"),
        unit="piece",
        price="92.00",
        amount="276,000.00",
        totals=("276,000.00", "41,400.00", "317,400.00"),
        tin=("105458053391", "000570541-0101"),
        adv=("40", "40%" + _ADV),
        pay=(30, 30, "balance 60% within 30 days of delivery"),
        deliv=(25, "Delivery within 25 days of PO"),
        pen=("1", "penalty of 1% of order value per week"),
        valid=(30, "valid for 30 days from the date above"),
    ),
    6: _pack(
        supplier="Teesta Fabrics Ltd",
        qno="QT-2026-906",
        date="2026-10-26",
        item="A",
        desc="Cotton twill fabric, 280 gsm",
        qty=("12000", "12,000"),
        unit="metre",
        price="465.00",
        amount="5,580,000.00",
        totals=("5,580,000.00", "837,000.00", "6,417,000.00"),
        tin=("106458063391", "000670641-0101"),
        adv=("10", "10%" + _ADV),
        pay=(60, 60, "Balance within 60 days of delivery"),
        deliv=(27, "Delivery within 27 days of PO"),
        pen=None,
        valid=(30, "valid for 30 days from the date above"),
    ),
    7: _pack(
        supplier="Rupsha Zipper Factory",
        qno="QT-2026-907",
        date="2026-10-20",
        item="B",
        desc="Metal zipper, 18 cm",
        qty=("16500", "16,500"),
        unit="piece",
        price="35.00",
        amount="577,500.00",
        totals=("577,500.00", "86,625.00", "664,125.00"),
        tin=("107458073391", "000770741-0101"),
        adv=("0", _NO_ADV),
        pay=(45, 45, "Payment within 45 days of delivery"),
        deliv=(22, "Delivery within 22 days of PO"),
        pen=("0.5", "penalty: 0.5% of order value per week"),
        valid=(35, "valid for 35 days from the date above"),
    ),
    8: _pack(
        supplier="Bhairab Thread and Co",
        qno="QT-2026-908",
        date="2026-10-21",
        item="C",
        desc="Polyester sewing thread, cone",
        qty=("800", "800"),
        unit="cone",
        price="205.00",
        amount="164,000.00",
        totals=("164,000.00", "24,600.00", "188,600.00"),
        tin=None,
        adv=("10", "10%" + _ADV),
        pay=(30, 30, "Payment within 30 days of delivery"),
        deliv=(18, "Delivery within 18 days of PO"),
        pen=("0.5", "penalty of 0.5% per week of delay"),
        valid=(30, "valid for 30 days from the date above"),
    ),
    9: _pack(
        supplier="Dhaleshwari Poly Pack",
        qno="QT-2026-909",
        date="2026-10-22",
        item="D",
        desc="Poly bag, 30 x 40 cm",
        qty=("50000", "50,000"),
        unit="piece",
        price="6.40",
        amount="322,000.00",
        totals=("322,000.00", "48,300.00", "370,300.00"),
        tin=("109458093391", "000970941-0101"),
        adv=("5", "5%" + _ADV),
        pay=(30, 90, "Payment within 30 to 90 days as agreed by both parties"),
        deliv=(28, "Delivery within 4 weeks of PO"),
        pen=("0.5", "penalty of 0.5% of order value per week"),
        valid=(30, "valid for 30 days from the date above"),
    ),
    10: _pack(
        supplier="Kushiyara Box Industries",
        qno="QT-2026-910",
        date="2026-10-23",
        item="E",
        desc="Carton box, 5-ply",
        qty=("3000", "3,000"),
        unit="piece",
        price="94.00",
        amount="282,000.00",
        totals=None,
        tin=("110458103391", "001071041-0101"),
        adv=("10", "10%" + _ADV),
        pay=(45, 45, "Payment within 45 days of delivery"),
        deliv=(60, "Delivery within 60 days of PO"),
        pen=("0.5", "penalty of 0.5% of order value per week"),
        valid=(30, "valid for 30 days from the date above"),
    ),
}
