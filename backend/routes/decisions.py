"""Append-only analyst decisions and audit history."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.db import application_connection
from backend.security import CurrentUser, get_current_user, require_demo_write_access, require_roles
from backend.schemas import AnalystFeedbackCreate, DecisionCreate
from core.intervention import load_policy
from core.simulator import TransactionSimulator
from core.taint import calculate_proportional_taint

router = APIRouter(prefix="/decisions", tags=["decisions", "audit"], dependencies=[Depends(get_current_user)])


@router.post("", status_code=201, dependencies=[Depends(require_demo_write_access), Depends(require_roles("analyst", "risk_manager", "admin"))])
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
        db.execute(
            "INSERT INTO case_audit_events (scenario_id, timestamp, actor, role, action, result) VALUES (?, ?, ?, ?, ?, ?)",
            (payload.scenario_id, created_at, payload.actor, "analyst", "Decision submitted",
             f"{payload.decision} · {payload.reason}"),
        )
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


@router.post("/{decision_id}/feedback", status_code=201, dependencies=[Depends(require_demo_write_access), Depends(require_roles("analyst", "risk_manager", "admin"))])
def create_analyst_feedback(decision_id: int, payload: AnalystFeedbackCreate) -> dict:
    """Append a single validated feedback record for an existing decision."""
    created_at = datetime.now(timezone.utc).isoformat()
    with application_connection() as db:
        exists = db.execute("SELECT 1 FROM analyst_decisions WHERE decision_id = ?", (decision_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Analyst decision was not found.")
        try:
            cursor = db.execute(
                """INSERT INTO analyst_feedback
                (decision_id, was_useful, recommendation_feedback, trace_accuracy, confidence, reason, actor, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (decision_id, payload.was_useful, payload.recommendation_feedback, payload.trace_accuracy,
                 payload.confidence, payload.reason, payload.actor, created_at),
            )
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise HTTPException(status_code=409, detail="Feedback for this decision has already been recorded.") from exc
            raise
    return {"feedback_id": cursor.lastrowid, "decision_id": decision_id, **payload.model_dump(),
            "created_at": created_at, "synthetic": True, "append_only": True}


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


@router.get("/{scenario_id}/audit")
def list_case_audit(scenario_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Return a readable, case-scoped audit timeline without credentials or secrets."""
    with application_connection() as db:
        rows = db.execute(
            "SELECT event_id, scenario_id, timestamp, actor, role, action, result, synthetic "
            "FROM case_audit_events WHERE scenario_id = ? ORDER BY timestamp, event_id",
            (scenario_id,),
        ).fetchall()
        decisions = db.execute(
            "SELECT decision_id, created_at, actor, decision, reason FROM analyst_decisions "
            "WHERE scenario_id = ? ORDER BY created_at, decision_id", (scenario_id,)
        ).fetchall()
    events = [dict(row) for row in rows]
    if not events:
        with application_connection() as db:
            incident = db.execute("SELECT reported_at, analysis_at FROM incidents WHERE scenario_id = ? LIMIT 1", (scenario_id,)).fetchone()
        if incident:
            base = incident["reported_at"]
            events = [
                {"event_id": f"demo-{index}", "scenario_id": scenario_id, "timestamp": stamp,
                 "actor": actor, "role": role, "action": action, "result": result, "synthetic": True}
                for index, (stamp, actor, role, action, result) in enumerate([
                    (base, "FlowFreeze", "system", "Case created", "Synthetic alert received"),
                    (base, "FlowFreeze", "system", "Risk scored", "Explainable risk signals prepared"),
                    (incident["analysis_at"] or base, "FlowFreeze", "system", "Investigation prepared", "Graph, exposure and next-move views available"),
                ], start=1)
            ]
    for row in decisions:
        events.append({"event_id": f"decision-{row['decision_id']}", "scenario_id": scenario_id,
                       "timestamp": row["created_at"], "actor": row["actor"], "role": "analyst",
                       "action": "Analyst decision recorded", "result": f"{row['decision']} · {row['reason']}",
                       "synthetic": True})
    events.sort(key=lambda item: (item["timestamp"], str(item["event_id"])))
    return {"synthetic": True, "scenario_id": scenario_id, "events": events,
            "viewer_role": user.role}
