"""Shared by both extractors: `vat_shown_separately` is derived from evidence, never asserted."""

from __future__ import annotations

from docgate.extraction.base import Candidate, Outcome, absent, found, unreadable


def derive_vat_flag(vat_amount: Candidate, tax_inclusive: Candidate) -> Candidate:
    """True needs a VAT line. False needs a verified "taxes included" statement and no VAT line.

    Anything else stays ABSENT or UNREADABLE so rule H5 sees UNKNOWN, never a guessed False.
    """
    if vat_amount.outcome is Outcome.UNREADABLE or tax_inclusive.outcome is Outcome.UNREADABLE:
        return unreadable("VAT presentation could not be read reliably")
    vat_found = vat_amount.outcome is Outcome.FOUND
    incl_found = tax_inclusive.outcome is Outcome.FOUND
    if vat_found and incl_found:
        return unreadable("both a VAT line and a 'taxes included' statement are present")
    if vat_found:
        return found(True, vat_amount.quote or "")
    if incl_found:
        return found(False, tax_inclusive.quote or "")
    return absent("neither a VAT line nor a 'taxes included' statement")
