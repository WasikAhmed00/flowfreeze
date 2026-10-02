"""Synthetic demo inventory and explicit development-only reset endpoint."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query

from backend.db import initialize_application_tables, resolve_database_path
from data_generator.config import DEFAULT_DATA_DIR, DEFAULT_RANDOM_SEED
from data_generator.generate import generate_dataset

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("")
def demo_scenarios(limit: int = Query(default=8, ge=1, le=50)) -> dict:
    from backend.db import application_connection

    with application_connection() as db:
        rows = db.execute(
            "SELECT scenario_id, incident_id, incident_type, scenario_type, reported_at FROM incidents ORDER BY scenario_type, scenario_id LIMIT ?",
            (limit,),
        ).fetchall()
    return {"synthetic": True, "scenarios": [dict(row) for row in rows]}


@router.post("/reset")
def reset_demo(seed: int = Query(default=DEFAULT_RANDOM_SEED, ge=0, le=2**32 - 1)) -> dict:
    if os.environ.get("APP_ENV", "development").lower() != "development":
        raise HTTPException(status_code=403, detail="Demo reset is available only when APP_ENV=development.")
    expected_database = (DEFAULT_DATA_DIR / "flowfreeze.db").resolve()
    if resolve_database_path() != expected_database:
        raise HTTPException(
            status_code=409,
            detail="Demo reset currently supports only the default data/flowfreeze.db location.",
        )
    counts = generate_dataset(DEFAULT_DATA_DIR, seed)
    initialize_application_tables()
    return {
        "status": "reset",
        "seed": seed,
        "counts": counts,
        "warning": "Reset replaces the synthetic SQLite database, including its local audit history.",
    }
