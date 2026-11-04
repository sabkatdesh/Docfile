"""Plain-English name of the condition each rule tests, built from the config thresholds."""

from __future__ import annotations

from docgate.domain.config import RuleConfig


def rule_titles(cfg: RuleConfig) -> dict[str, str]:
    return {
        "R1": f"Unit price more than {cfg.price_tolerance_pct}% above the PR maximum",
        "R2": f"Advance payment more than {cfg.advance_max_pct}%",
        "R3": f"No late-delivery penalty of at least {cfg.penalty_min_pct_per_week}% per week",
        "R4": "TIN or BIN missing",
        "R5": f"Delivery later than {cfg.delivery_max_days} days after the PO",
        "H1": f"Unit price above the PR maximum by up to {cfg.price_tolerance_pct}%",
        "H2": f"Quantity differs from the PR by more than {cfg.qty_tolerance_pct}%",
        "H3": (
            "Payment terms unclear or outside "
            f"{cfg.payment_min_days}-{cfg.payment_max_days} days after delivery"
        ),
        "H4": f"Delivery in {cfg.delivery_review_above_days + 1}-{cfg.delivery_max_days} days",
        "H5": f"VAT not shown separately at {cfg.vat_rate_pct}%",
        "H6": "Numbers do not add up",
        "H7": f"Quotation valid for less than {cfg.validity_min_days} days",
    }
