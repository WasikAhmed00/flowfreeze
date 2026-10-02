"""Synthetic incident list and detail endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.db import application_connection

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("")
def list_incidents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    scenario_type: str | None = Query(default=None, max_length=80),
    status: str | None = Query(default=None, max_length=40),
) -> dict:
    clauses: list[str] = []
    params: list[object] = []
    if scenario_type:
        clauses.append("scenario_type = ?")
        params.append(scenario_type)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with application_connection() as db:
        total = db.execute(f"SELECT COUNT(*) FROM incidents{where}", params).fetchone()[0]
        rows = db.execute(
            f"SELECT * FROM incidents{where} ORDER BY reported_at DESC, incident_id LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return {"synthetic": True, "total": total, "limit": limit, "offset": offset, "incidents": [dict(row) for row in rows]}


@router.get("/{scenario_id}")
def get_incident(scenario_id: str) -> dict:
    with application_connection() as db:
        row = db.execute(
            "SELECT * FROM incidents WHERE scenario_id = ? ORDER BY incident_id LIMIT 1",
            (scenario_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Incident scenario not found.")
        transaction_count = db.execute(
            "SELECT COUNT(*) FROM transactions WHERE scenario_id = ?", (scenario_id,)
        ).fetchone()[0]
        wallet_count = db.execute(
            "SELECT COUNT(*) FROM wallets WHERE scenario_id = ?", (scenario_id,)
        ).fetchone()[0]
    return {"synthetic": True, "incident": dict(row), "transaction_count": transaction_count, "wallet_count": wallet_count}
