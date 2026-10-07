"""Incident analysis endpoint combining replay, graph, taint, and policy."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.pipeline import analyze_scenario
from backend.security import get_current_user

router = APIRouter(prefix="/analysis", tags=["analysis"], dependencies=[Depends(get_current_user)])


@router.get("/{scenario_id}")
def analyze(
    scenario_id: str,
    fraud_risk: float | None = Query(default=None, ge=0, le=1),
    p_forward: float | None = Query(default=None, ge=0, le=1),
    p_cashout: float | None = Query(default=None, ge=0, le=1),
    p_no_movement: float | None = Query(default=None, ge=0, le=1),
) -> dict:
    moves = (p_forward, p_cashout, p_no_movement)
    if any(value is not None for value in moves) and not all(value is not None for value in moves):
        raise HTTPException(status_code=422, detail="Supply all three next-move probabilities together.")
    probabilities = None
    if p_forward is not None:
        probabilities = {"forward": p_forward, "cashout": p_cashout, "no_movement": p_no_movement}
        if abs(sum(probabilities.values()) - 1) > 0.02:
            raise HTTPException(status_code=422, detail="Next-move probabilities must sum to 1 within 0.02.")
    try:
        return analyze_scenario(scenario_id, fraud_risk=fraud_risk, next_move_probabilities=probabilities)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
