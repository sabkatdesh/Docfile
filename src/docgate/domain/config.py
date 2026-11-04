"""Every business threshold lives here, so rules hold no magic numbers."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class RuleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    # R1/H1: price above PR max by more than this is Reject; up to this is Needs person.
    price_tolerance_pct: Decimal = Decimal("3")
    # R2: advance payment above this is Reject.
    advance_max_pct: Decimal = Decimal("20")
    # R3: late-delivery penalty below this (% of order value per week) counts as no clause.
    penalty_min_pct_per_week: Decimal = Decimal("0.5")
    # R5: delivery later than this is Reject.
    delivery_max_days: int = 45
    # H4: delivery above this (and within delivery_max_days) is Needs person.
    delivery_review_above_days: int = 30
    # H2: quantity differs from the PR by more than this, either direction.
    qty_tolerance_pct: Decimal = Decimal("5")
    # H3: payment terms must fall inside this window (days after delivery).
    payment_min_days: int = 30
    payment_max_days: int = 60
    # H7: validity shorter than this is Needs person.
    validity_min_days: int = 30
    # H5: VAT must be shown separately at this rate.
    vat_rate_pct: Decimal = Decimal("15")
    # H5/H6: absolute BDT slack when comparing computed vs quoted amounts (paise rounding).
    arithmetic_tolerance: Decimal = Decimal("0.01")
    # "4 weeks" is 28 days.
    days_per_week: int = 7

    @field_validator("*", mode="before")
    @classmethod
    def _no_floats(cls, v: object) -> object:
        if isinstance(v, float):
            raise ValueError("thresholds must be Decimal, str or int, never float")
        return v


DEFAULT_CONFIG = RuleConfig()
