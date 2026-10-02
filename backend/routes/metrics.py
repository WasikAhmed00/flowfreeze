"""Synthetic-only project and decision outcome metrics."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path

from fastapi import APIRouter

from backend.db import application_connection

router = APIRouter(prefix="/metrics", tags=["metrics"])
ML_METRICS_PATH = Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "metrics.json"
END_TO_END_METRICS_PATH = Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "end_to_end_metrics.json"


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
    try:
        ml_metrics = json.loads(ML_METRICS_PATH.read_text(encoding="utf-8")) if ML_METRICS_PATH.exists() else None
    except (OSError, json.JSONDecodeError):
        ml_metrics = None
    try:
        end_to_end = json.loads(END_TO_END_METRICS_PATH.read_text(encoding="utf-8")) if END_TO_END_METRICS_PATH.exists() else None
    except (OSError, json.JSONDecodeError):
        end_to_end = None
    return {
        "synthetic": True,
        "dataset": {"incident_count": incidents, "transaction_count": transactions, "wallet_count": wallets},
        "audit": {"decision_count": decisions, "decision_counts": decision_counts},
        "simulations": {
            "count": len(simulations),
            "estimated_tainted_value_preserved_bdt": f"{sum((Decimal(row[0]) for row in simulations), Decimal('0.00')):.2f}",
            "estimated_legitimate_value_affected_bdt": f"{sum((Decimal(row[1]) for row in simulations), Decimal('0.00')):.2f}",
        },
        "ml_evaluation": {
            "metrics_available": ml_metrics is not None,
            "artifact_available": (ML_METRICS_PATH.parent / "fraud_model.joblib").exists()
            and (ML_METRICS_PATH.parent / "next_move_model.joblib").exists(),
            "synthetic_only": True,
            "held_out_test": ml_metrics.get("held_out_test") if ml_metrics else None,
            "metadata": {
                key: ml_metrics.get(key)
                for key in ("seed", "split_scenarios", "split_wallet_rows", "fraud_model_selection")
            } if ml_metrics else None,
            "warning": ml_metrics.get("warning") if ml_metrics else "Train with python -m ml.train to generate held-out synthetic metrics.",
        },
        "end_to_end_evaluation": {
            "metrics_available": end_to_end is not None,
            "results": end_to_end,
            "warning": end_to_end.get("limitation") if end_to_end else "Run python -m core.baseline to compare the direct-recipient baseline with FlowFreeze on held-out synthetic cases.",
        },
        "warning": "Synthetic scenario metrics are not upay BD production statistics.",
    }
