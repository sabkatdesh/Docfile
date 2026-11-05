"""Pydantic schemas from SPEC section 4. No logic beyond invariants."""

from __future__ import annotations

import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic import Field as PydanticField


class FieldStatus(StrEnum):
    OK = "OK"
    MISSING = "MISSING"
    UNVERIFIED = "UNVERIFIED"
    CONFLICT = "CONFLICT"


class Field[T](BaseModel):
    """An extracted value. It exists only with a verified quote; otherwise it is UNKNOWN."""

    model_config = ConfigDict(frozen=True)

    value: T | None = None
    quote: str | None = None
    status: FieldStatus = FieldStatus.MISSING

    @property
    def is_ok(self) -> bool:
        return self.status is FieldStatus.OK

    @field_validator("value", mode="before")
    @classmethod
    def _no_floats(cls, v: Any) -> Any:
        if isinstance(v, float):
            raise ValueError("float is not allowed; use Decimal")
        return v

    @model_validator(mode="after")
    def _check_invariant(self) -> Self:
        if self.status is FieldStatus.OK:
            if self.value is None or not self.quote:
                raise ValueError("an OK field needs both a value and a quote")
        elif self.value is not None:
            raise ValueError(f"a {self.status} field must not carry a value")
        return self


class DayRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    min: int
    max: int

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.min > self.max:
            raise ValueError("min must not exceed max")
        return self


def _missing[T]() -> Field[T]:
    return Field[T]()


class Extraction(BaseModel):
    """Everything the checker reads from one supplier pack. Absent fields stay MISSING."""

    supplier: Field[str] = PydanticField(default_factory=_missing)
    quotation_no: Field[str] = PydanticField(default_factory=_missing)
    date: Field[datetime.date] = PydanticField(default_factory=_missing)
    item_code: Field[str] = PydanticField(default_factory=_missing)
    description: Field[str] = PydanticField(default_factory=_missing)
    qty: Field[Decimal] = PydanticField(default_factory=_missing)
    unit: Field[str] = PydanticField(default_factory=_missing)
    unit_price: Field[Decimal] = PydanticField(default_factory=_missing)
    subtotal: Field[Decimal] = PydanticField(default_factory=_missing)
    vat_amount: Field[Decimal] = PydanticField(default_factory=_missing)
    total: Field[Decimal] = PydanticField(default_factory=_missing)
    vat_shown_separately: Field[bool] = PydanticField(default_factory=_missing)
    tin: Field[str] = PydanticField(default_factory=_missing)
    bin: Field[str] = PydanticField(default_factory=_missing)
    advance_pct: Field[Decimal] = PydanticField(default_factory=_missing)
    payment_days: Field[DayRange] = PydanticField(default_factory=_missing)
    delivery_days: Field[int] = PydanticField(default_factory=_missing)
    penalty_pct_per_week: Field[Decimal] = PydanticField(default_factory=_missing)
    validity_days: Field[int] = PydanticField(default_factory=_missing)


class PRLine(BaseModel):
    """One requested item from the purchase request."""

    model_config = ConfigDict(frozen=True)

    pr_number: str
    item_code: str
    description: str
    unit: str
    qty: Decimal = PydanticField(gt=0)
    max_unit_price: Decimal = PydanticField(gt=0)


class RuleStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class Decision(StrEnum):
    APPROVE = "Approve"
    REJECT = "Reject"
    NEEDS_PERSON = "Needs a person to check"


class RuleResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    status: RuleStatus
    message: str
    evidence_quote: str | None = None


class HumanReview(BaseModel):
    """A reviewer's answer to a paused pack. It never replaces the machine verdict."""

    model_config = ConfigDict(frozen=True)

    decision: Decision
    reason: str
    reviewer: str
    reviewed_at: datetime.datetime

    @field_validator("decision")
    @classmethod
    def _final_decision(cls, v: Decision) -> Decision:
        if v is Decision.NEEDS_PERSON:
            raise ValueError("a human decision must be Approve or Reject")
        return v

    @field_validator("reason", "reviewer")
    @classmethod
    def _not_blank(cls, v: str, info: ValidationInfo) -> str:
        text = v.strip()
        if not text:
            raise ValueError(f"{info.field_name} must not be empty")
        return text

    @field_validator("reviewed_at")
    @classmethod
    def _aware(cls, v: datetime.datetime) -> datetime.datetime:
        if v.tzinfo is None:
            raise ValueError("reviewed_at needs a timezone")
        return v


class Verdict(BaseModel):
    decision: Decision
    reason: str
    rule_results: list[RuleResult]
    human_review: HumanReview | None = None

    @property
    def needs_human(self) -> bool:
        return self.decision is Decision.NEEDS_PERSON

    @property
    def human_decision(self) -> Decision | None:
        return self.human_review.decision if self.human_review else None


ErrorKind = Literal["error", "config"]


class NodeError(BaseModel):
    """A pipeline step failed. `config` marks an operator problem (bad key, budget) that stops a
    batch; anything else escalates just that pack."""

    model_config = ConfigDict(frozen=True)

    node: str
    kind: ErrorKind
    message: str
