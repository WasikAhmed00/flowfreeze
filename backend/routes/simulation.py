"""Estimate outcomes for recorded analyst decisions without changing ledgers."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from backend.db import application_connection
from backend.security import get_current_user, require_demo_write_access
from core.simulator import TransactionSimulator
from core.taint import calculate_proportional_taint
from core.intelligence import simulate_what_if
from backend.pipeline import analyze_scenario
from backend.schemas import WhatIfRequest

router = APIRouter(prefix="/simulation", tags=["simulation"], dependencies=[Depends(get_current_user)])


@router.post("/what-if")
def what_if(payload: WhatIfRequest) -> dict:
    try:
        analysis = analyze_scenario(payload.scenario_id)
        replay = TransactionSimulator().replay(payload.scenario_id)
        taint = calculate_proportional_taint(replay)
        result = simulate_what_if(
            analysis["intelligence"], taint, action=payload.action,
            source_wallet=payload.source_wallet, target_wallet=payload.target_wallet,
            amount=float(payload.amount_bdt),
        )
        return {"scenario_id": payload.scenario_id, **result}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{decision_id}", status_code=201, dependencies=[Depends(require_demo_write_access)])
def simulate_decision(decision_id: int) -> dict:
    with application_connection() as db:
        decision = db.execute("SELECT * FROM analyst_decisions WHERE decision_id = ?", (decision_id,)).fetchone()
        if decision is None:
            raise HTTPException(status_code=404, detail="Decision not found.")
        if db.execute("SELECT 1 FROM simulated_outcomes WHERE decision_id = ?", (decision_id,)).fetchone():
            raise HTTPException(status_code=409, detail="This decision already has a simulated outcome.")

    try:
        replay = TransactionSimulator().replay(str(decision["scenario_id"]))
        taint = calculate_proportional_taint(replay)
    except (KeyError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    wallet = next((item for item in taint.wallets if item.wallet_id == decision["wallet_id"]), None)
    if wallet is None:
        raise HTTPException(status_code=409, detail="Target wallet is no longer present in the scenario snapshot.")

    amount = Decimal(str(decision["proposed_amount_bdt"]))
    if decision["decision"] == "reject":
        amount = Decimal("0.00")
    tainted_preserved = min(amount, wallet.potentially_tainted_bdt)
    legitimate_affected = max(Decimal("0.00"), amount - tainted_preserved)
    created_at = datetime.now(timezone.utc).isoformat()
    with application_connection() as db:
        cursor = db.execute(
            """INSERT INTO simulated_outcomes
            (decision_id, scenario_id, wallet_id, simulated_amount_bdt,
             estimated_tainted_preserved_bdt, estimated_legitimate_affected_bdt, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (decision_id, decision["scenario_id"], decision["wallet_id"], f"{amount:.2f}",
             f"{tainted_preserved:.2f}", f"{legitimate_affected:.2f}", created_at),
        )
        simulation_id = cursor.lastrowid
    return {
        "simulation_id": simulation_id,
        "decision_id": decision_id,
        "scenario_id": decision["scenario_id"],
        "wallet_id": decision["wallet_id"],
        "decision": decision["decision"],
        "simulated_amount_bdt": f"{amount:.2f}",
        "estimated_tainted_preserved_bdt": f"{tainted_preserved:.2f}",
        "estimated_legitimate_affected_bdt": f"{legitimate_affected:.2f}",
        "created_at": created_at,
        "synthetic": True,
        "ledger_changed": False,
    }
