"""Synthetic-only project and decision outcome metrics."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.db import application_connection
from backend.telemetry import snapshot as api_snapshot
from core.business_impact import run_business_impact
from core.shadow_mode import run_shadow_mode

router = APIRouter(prefix="/metrics", tags=["metrics"])
ML_METRICS_PATH = Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "metrics.json"
REAL_MODEL_METADATA_PATH = Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "real_model_metadata.json"
ROBUSTNESS_METRICS_PATH = Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "robustness.json"
END_TO_END_METRICS_PATH = Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "end_to_end_metrics.json"
IMPACT_METRICS_PATH = Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "impact_analysis.json"


@router.get("")
def get_metrics() -> dict:
    with application_connection() as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        incidents = db.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] if "incidents" in tables else 0
        transactions = db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] if "transactions" in tables else 0
        wallets = db.execute("SELECT COUNT(*) FROM wallets").fetchone()[0] if "wallets" in tables else 0
        decisions = db.execute("SELECT COUNT(*) FROM analyst_decisions").fetchone()[0]
        simulations = db.execute(
            "SELECT estimated_tainted_preserved_bdt, estimated_legitimate_affected_bdt FROM simulated_outcomes"
        ).fetchall()
        decision_counts = {
            row["decision"]: row["count"]
            for row in db.execute("SELECT decision, COUNT(*) AS count FROM analyst_decisions GROUP BY decision")
        }
        stream_transactions = db.execute("SELECT COUNT(*) FROM flow_transactions").fetchone()[0] if "flow_transactions" in tables else 0
        stream_alerts = db.execute("SELECT COUNT(*) FROM flow_transactions WHERE alerts_json != '[]'").fetchone()[0] if "flow_transactions" in tables else 0
        case_count = db.execute("SELECT COUNT(*) FROM investigation_cases").fetchone()[0] if "investigation_cases" in tables else 0
        open_case_count = db.execute("SELECT COUNT(*) FROM investigation_cases WHERE status NOT IN ('resolved', 'closed')").fetchone()[0] if "investigation_cases" in tables else 0
    try:
        ml_metrics = json.loads(ML_METRICS_PATH.read_text(encoding="utf-8")) if ML_METRICS_PATH.exists() else None
    except (OSError, json.JSONDecodeError):
        ml_metrics = None
    try:
        real_metadata = json.loads(REAL_MODEL_METADATA_PATH.read_text(encoding="utf-8")) if REAL_MODEL_METADATA_PATH.exists() else None
    except (OSError, json.JSONDecodeError):
        real_metadata = None
    try:
        robustness_metrics = json.loads(ROBUSTNESS_METRICS_PATH.read_text(encoding="utf-8")) if ROBUSTNESS_METRICS_PATH.exists() else None
    except (OSError, json.JSONDecodeError):
        robustness_metrics = None
    try:
        end_to_end = json.loads(END_TO_END_METRICS_PATH.read_text(encoding="utf-8")) if END_TO_END_METRICS_PATH.exists() else None
    except (OSError, json.JSONDecodeError):
        end_to_end = None
    try:
        impact_analysis = json.loads(IMPACT_METRICS_PATH.read_text(encoding="utf-8")) if IMPACT_METRICS_PATH.exists() else None
    except (OSError, json.JSONDecodeError):
        impact_analysis = None
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
        "real_public_model": {
            "available": (REAL_MODEL_METADATA_PATH.parent / "real_fraud_model.joblib").exists(),
            "metadata": real_metadata,
            "synthetic": False,
            "warning": "Public Fraud.csv is not upay BD production/customer data; FlowFreeze scenarios remain synthetic.",
        },
        "robustness": robustness_metrics,
        "end_to_end_evaluation": {
            "metrics_available": end_to_end is not None,
            "results": end_to_end,
            "warning": end_to_end.get("limitation") if end_to_end else "Run python -m core.baseline to compare the direct-recipient baseline with FlowFreeze on held-out synthetic cases.",
        },
        "financial_impact": {
            "metrics_available": impact_analysis is not None,
            "synthetic_data": True,
            "results": impact_analysis,
            "warning": "Synthetic exposure estimates are not actual financial loss, observed prevention, customer impact, or upay BD production performance.",
        },
        "warning": "Synthetic scenario metrics are not upay BD production statistics.",
        "operational": {
            "status": "ok",
            "api": api_snapshot(),
            "stream_transactions_total": stream_transactions,
            "stream_transactions_with_alerts": stream_alerts,
            "cases_total": case_count,
            "open_cases": open_case_count,
            "synthetic_only": True,
        },
    }


@router.get("/business-impact")
def get_business_impact() -> dict:
    """Return a fresh, synthetic-only impact simulation from generated CSV data."""
    return run_business_impact()


@router.get("/shadow-mode")
def get_shadow_mode() -> dict:
    """Return synthetic shadow-mode results plus any analyst feedback collected locally."""
    result = run_shadow_mode()
    with application_connection() as db:
        rows = db.execute(
            """SELECT d.decision, f.was_useful, f.recommendation_feedback, f.trace_accuracy, f.confidence
            FROM analyst_feedback f JOIN analyst_decisions d ON d.decision_id = f.decision_id"""
        ).fetchall()
    count = len(rows)
    result["feedback_summary"] = {
        "feedback_records": count,
        "analyst_agreement_rate": round(sum(1.0 if row["decision"] == "approve" else 0.5 if row["decision"] == "modify" else 0.0 for row in rows) / count, 4) if count else None,
        "recommendation_helpful_rate": round(sum(row["recommendation_feedback"] == "helpful" for row in rows) / count, 4) if count else None,
        "override_rate": round(sum(row["decision"] in {"reject", "modify"} for row in rows) / count, 4) if count else None,
        "usefulness_counts": {value: sum(row["was_useful"] == value for row in rows) for value in ("yes", "partially", "no")},
        "trace_accuracy_counts": {value: sum(row["trace_accuracy"] == value for row in rows) for value in ("accurate", "partially_accurate", "inaccurate")},
        "confidence_counts": {value: sum(row["confidence"] == value for row in rows) for value in ("low", "medium", "high")},
        "synthetic_records_only": True,
    }
    result["human"] = {**result["human"], "analyst_agreement_rate": result["feedback_summary"]["analyst_agreement_rate"],
                        "recommendation_override_rate": result["feedback_summary"]["override_rate"],
                        "recommendation_usefulness_rate": result["feedback_summary"]["recommendation_helpful_rate"]}
    return result
@router.get("/impact/{scenario_id}")
def get_scenario_impact(scenario_id: str) -> dict:
    """Calculate direct-only vs. multi-hop impact and delay snapshots for one case."""
    from core.impact_analysis import analyze_scenario_impact

    try:
        return analyze_scenario_impact(scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
