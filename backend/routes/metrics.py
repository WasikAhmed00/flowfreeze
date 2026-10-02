"""Synthetic-only project and decision outcome metrics."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter

from backend.db import application_connection

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
def get_metrics() -> dict:
    with application_connection() as db:
        incidents = db.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        transactions = db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        wallets = db.execute("SELECT COUNT(*) FROM wallets").fetchone()[0]
        decisions = db.execute("SELECT COUNT(*) FROM analyst_decisions").fetchone()[0]
        simulations = db.execute(
            "SELECT estimated_tainted_preserved_bdt, estimated_legitimate_affected_bdt FROM simulated_outcomes"
        ).fetchall()
        decision_counts = {
            row["decision"]: row["count"]
            for row in db.execute("SELECT decision, COUNT(*) AS count FROM analyst_decisions GROUP BY decision")
        }
    return {
        "synthetic": True,
        "dataset": {"incident_count": incidents, "transaction_count": transactions, "wallet_count": wallets},
        "audit": {"decision_count": decisions, "decision_counts": decision_counts},
        "simulations": {
            "count": len(simulations),
            "estimated_tainted_value_preserved_bdt": f"{sum((Decimal(row[0]) for row in simulations), Decimal('0.00')):.2f}",
            "estimated_legitimate_value_affected_bdt": f"{sum((Decimal(row[1]) for row in simulations), Decimal('0.00')):.2f}",
        },
        "warning": "Synthetic scenario metrics are not upay BD production statistics.",
    }
