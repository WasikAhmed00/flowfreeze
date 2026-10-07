"""Basic synthetic case-management adapter endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status

from backend.db import application_connection
from backend.schemas import CaseCreate, CasePatch

router = APIRouter(prefix="/cases", tags=["cases"])


def _case(row) -> dict:
    return {"id": row["case_id"], "case_id": row["case_id"],
            "transaction_id": row["transaction_id"], "risk_score": row["risk_score"],
            "investigator": row["investigator"], "status": row["status"],
            "title": row["title"], "notes": row["notes"],
            "created_at": row["created_at"], "updated_at": row["updated_at"], "synthetic": True}


def _lookup(db, case_id: str):
    return db.execute("SELECT * FROM investigation_cases WHERE case_id = ?", (case_id,)).fetchone()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    risk = payload.risk_score
    with application_connection() as db:
        if payload.transaction_id:
            tx = db.execute("SELECT risk_score FROM flow_transactions WHERE transaction_id = ?", (payload.transaction_id,)).fetchone()
            if tx is None:
                raise HTTPException(status_code=404, detail="Linked stream transaction was not found.")
            if risk is None:
                risk = float(tx["risk_score"])
        if risk is None:
            risk = 0.0
        cursor = db.execute(
            "INSERT INTO investigation_cases (case_id, transaction_id, risk_score, investigator, status, title, notes, created_at, updated_at) "
            "VALUES ('pending', ?, ?, ?, ?, ?, ?, ?, ?)",
            (payload.transaction_id, risk, payload.investigator, payload.status,
             payload.title, payload.notes, now, now),
        )
        case_id = f"FF-{cursor.lastrowid:08d}"
        db.execute("UPDATE investigation_cases SET case_id = ? WHERE id = ?", (case_id, cursor.lastrowid))
        row = _lookup(db, case_id)
        return _case(row)


@router.get("")
def list_cases(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0),
              status_filter: str | None = Query(default=None, alias="status", max_length=30)) -> dict:
    with application_connection() as db:
        where = " WHERE status = ?" if status_filter else ""
        params = (status_filter,) if status_filter else ()
        total = db.execute(f"SELECT COUNT(*) FROM investigation_cases{where}", params).fetchone()[0]
        rows = db.execute(
            f"SELECT * FROM investigation_cases{where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    return {"synthetic": True, "total": total, "limit": limit, "offset": offset,
            "cases": [_case(row) for row in rows]}


@router.get("/{case_id}")
def get_case(case_id: str) -> dict:
    with application_connection() as db:
        row = _lookup(db, case_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return _case(row)


@router.patch("/{case_id}")
def update_case(case_id: str, payload: CasePatch) -> dict:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one case field must be supplied.")
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="Patched case fields cannot be null.")
    changes["updated_at"] = datetime.now(timezone.utc).isoformat()
    with application_connection() as db:
        if _lookup(db, case_id) is None:
            raise HTTPException(status_code=404, detail="Case not found.")
        fields = ", ".join(f"{field} = ?" for field in changes)
        db.execute(f"UPDATE investigation_cases SET {fields} WHERE case_id = ?",
                   (*changes.values(), case_id))
        row = _lookup(db, case_id)
    return _case(row)
