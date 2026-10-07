"""Validated API request and response models for the local demo backend."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


class DecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1, max_length=100)
    wallet_id: str = Field(min_length=1, max_length=100)
    decision: Literal["approve", "reject", "modify"]
    proposed_amount_bdt: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    reason: str = Field(min_length=3, max_length=1000)
    actor: str = Field(default="demo_analyst", min_length=1, max_length=100)


class DecisionRecord(BaseModel):
    decision_id: int
    scenario_id: str
    incident_id: str
    wallet_id: str
    decision: Literal["approve", "reject", "modify"]
    proposed_amount_bdt: Decimal
    reason: str
    actor: str
    created_at: str
    synthetic: bool = True


class AnalystFeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    was_useful: Literal["yes", "partially", "no"]
    recommendation_feedback: Literal["helpful", "not_helpful"]
    trace_accuracy: Literal["accurate", "partially_accurate", "inaccurate"]
    confidence: Literal["low", "medium", "high"]
    reason: str = Field(default="", max_length=1000)
    actor: str = Field(default="demo_analyst", min_length=1, max_length=100)


class HealthResponse(BaseModel):
    status: str
    synthetic_data_only: bool = True
    automatic_wallet_actions: bool = False
    database: str = "unknown"
    version: str = "0.2.0"


class TransactionCreate(BaseModel):
    """MFS-shaped, synthetic/de-identified event contract for adapter use."""
    model_config = ConfigDict(extra="forbid")

    transaction_id: str | None = Field(default=None, min_length=1, max_length=120)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sender_wallet: str = Field(min_length=1, max_length=120)
    receiver_wallet: str = Field(min_length=1, max_length=120)
    amount_bdt: Decimal = Field(validation_alias=AliasChoices("amount_bdt", "amount"),
                                ge=Decimal("0.01"), max_digits=14, decimal_places=2)
    transaction_type: Literal["transfer", "cashout", "cash_out", "withdrawal"] = "transfer"
    channel: str = Field(default="synthetic_api", min_length=1, max_length=80)

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone offset.")
        return value.astimezone(timezone.utc)

    @field_validator("sender_wallet", "receiver_wallet")
    @classmethod
    def wallet_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("wallet identifiers cannot be blank.")
        return value.strip()

    @model_validator(mode="after")
    def wallets_must_differ(self) -> "TransactionCreate":
        if self.sender_wallet == self.receiver_wallet:
            raise ValueError("sender_wallet and receiver_wallet must be different.")
        return self


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int = Field(default=1, ge=1, le=20)
    seed: int | None = None


class CaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transaction_id: str | None = Field(default=None, min_length=1, max_length=120)
    risk_score: float | None = Field(default=None, ge=0, le=1)
    investigator: str = Field(default="Unassigned", min_length=1, max_length=120)
    status: Literal["new", "investigating", "escalated", "resolved", "closed"] = "new"
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=2000)


class CasePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    risk_score: float | None = Field(default=None, ge=0, le=1)
    investigator: str | None = Field(default=None, min_length=1, max_length=120)
    status: Literal["new", "investigating", "escalated", "resolved", "closed"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class WhatIfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1, max_length=100)
    action: Literal["transfer", "cashout", "intervention"]
    source_wallet: str | None = Field(default=None, max_length=100)
    target_wallet: str | None = Field(default=None, max_length=100)
    amount_bdt: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
