"""Validated API request and response models for the local demo backend."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
