"""Append-only analyst decisions and audit history."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.db import application_connection
from backend.security import require_demo_write_access
from backend.schemas import DecisionCreate
from core.intervention import load_policy
from core.simulator import TransactionSimulator
from core.taint import calculate_proportional_taint

router = APIRouter(prefix="/decisions", tags=["decisions", "audit"])


@router.post("", status_code=201, dependencies=[Depends(require_demo_write_access)])
def create_decision(payload: DecisionCreate) -> dict:
    try:
        replay = TransactionSimulator().replay(payload.scenario_id)
        taint = calculate_proportional_taint(replay)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    wallet = next((item for item in taint.wallets if item.wallet_id == payload.wallet_id), None)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet is not a digital wallet in this scenario.")
    amount = payload.proposed_amount_bdt.quantize(Decimal("0.01"))
    if payload.decision == "reject" and amount != 0:
        raise HTTPException(status_code=422, detail="Rejected proposals must record an amount of zero.")
    if payload.decision in {"approve", "modify"}:
        if amount <= 0:
            raise HTTPException(status_code=422, detail="Approved or modified simulated amounts must be positive.")
        policy_limit = Decimal(str(load_policy()["maximum_simulated_hold_bdt"]))
        if amount > policy_limit or amount > wallet.balance_bdt:
            raise HTTPException(status_code=422, detail="Amount exceeds the current wallet balance or policy maximum.")

    incident_id = str(replay.incident["incident_id"])
    created_at = datetime.now(timezone.utc).isoformat()
    with application_connection() as db:
        cursor = db.execute(
            """INSERT INTO analyst_decisions
            (incident_id, scenario_id, wallet_id, decision, proposed_amount_bdt, reason, actor, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (incident_id, payload.scenario_id, payload.wallet_id, payload.decision,
             f"{amount:.2f}", payload.reason, payload.actor, created_at),
        )
        decision_id = cursor.lastrowid
    return {
        "decision_id": decision_id,
        "incident_id": incident_id,
        "scenario_id": payload.scenario_id,
        "wallet_id": payload.wallet_id,
        "decision": payload.decision,
        "proposed_amount_bdt": f"{amount:.2f}",
        "reason": payload.reason,
        "actor": payload.actor,
        "created_at": created_at,
        "synthetic": True,
        "automatic_execution": False,
    }


@router.get("")
def list_decisions(
    scenario_id: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    where = " WHERE scenario_id = ?" if scenario_id else ""
    params: list[object] = [scenario_id] if scenario_id else []
    with application_connection() as db:
        total = db.execute(f"SELECT COUNT(*) FROM analyst_decisions{where}", params).fetchone()[0]
        rows = db.execute(
            f"SELECT * FROM analyst_decisions{where} ORDER BY decision_id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return {"synthetic": True, "total": total, "decisions": [dict(row) for row in rows]}
