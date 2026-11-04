from decimal import Decimal

import pytest
from pydantic import ValidationError

from docgate.domain.config import DEFAULT_CONFIG, RuleConfig


def test_defaults_match_company_rules() -> None:
    c = DEFAULT_CONFIG
    assert c.price_tolerance_pct == Decimal("3")
    assert c.advance_max_pct == Decimal("20")
    assert c.penalty_min_pct_per_week == Decimal("0.5")
    assert c.delivery_max_days == 45
    assert c.delivery_review_above_days == 30
    assert c.qty_tolerance_pct == Decimal("5")
    assert c.payment_min_days == 30
    assert c.payment_max_days == 60
    assert c.validity_min_days == 30
    assert c.vat_rate_pct == Decimal("15")
    assert c.days_per_week == 7


def test_config_is_immutable() -> None:
    with pytest.raises(ValidationError):
        DEFAULT_CONFIG.price_tolerance_pct = Decimal("4")  # type: ignore[misc]


def test_config_rejects_float_thresholds() -> None:
    with pytest.raises(ValidationError):
        RuleConfig(price_tolerance_pct=3.0)
