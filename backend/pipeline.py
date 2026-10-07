"""Compose existing FlowFreeze analysis layers for backend/API consumers."""

from __future__ import annotations

from typing import Mapping

from core.graph import trace_downstream
from core.intervention import load_policy, recommend_intervention
from core.simulator import ReplayResult, TransactionSimulator
from core.taint import calculate_proportional_taint
from ml.predict import predict_scenario


def analyze_scenario(
    scenario_id: str,
    *,
    database_path: str | None = None,
    fraud_risk: float | None = None,
    next_move_probabilities: Mapping[str, float] | None = None,
) -> dict:
    """Return a consistent replay, graph, taint, and recommendation snapshot."""
    replay: ReplayResult = TransactionSimulator(database_path).replay(scenario_id)
    trace = trace_downstream(replay)
    taint = calculate_proportional_taint(replay)
    model_status: dict = {
        "synthetic": True,
        "source": "unavailable",
        "message": "Train the local models with python -m ml.train to enable risk and next-move predictions.",
    }
    wallet_risk = None
    wallet_moves = None
    if fraud_risk is not None or next_move_probabilities is not None:
        model_status = {
            "synthetic": True,
            "source": "user_supplied_illustrative_inputs",
            "message": "Caller-supplied scores are used as explicit illustrative inputs.",
        }
    else:
        try:
            predictions = predict_scenario(scenario_id)
            wallet_risk = {
                wallet_id: item["fraud_risk"]
                for wallet_id, item in predictions["wallet_predictions"].items()
            }
            wallet_moves = {
                wallet_id: item["next_move_probabilities"]
                for wallet_id, item in predictions["wallet_predictions"].items()
                if item.get("next_move_probabilities") is not None
            }
            if not wallet_moves:
                wallet_moves = None
            model_status = {
                "synthetic": predictions.get("synthetic", True),
                "source": predictions.get("fraud_model_source", "synthetic_flowfreeze_data"),
                "scenario_data_source": predictions.get("scenario_data_source", "synthetic_flowfreeze_scenario"),
                "fraud_model": predictions.get("fraud_model"),
                "fraud_threshold": predictions.get("fraud_threshold"),
                "next_move_model_source": predictions.get("next_move_model_source", "unavailable"),
                "wallet_risk_aggregation": predictions.get("wallet_risk_aggregation"),
                "message": predictions.get("warning"),
            }
        except FileNotFoundError:
            pass
    recommendation = recommend_intervention(
        replay,
        taint,
        trace,
        fraud_risk=fraud_risk,
        next_move_probabilities=next_move_probabilities,
        wallet_fraud_risk=wallet_risk,
        wallet_next_move_probabilities=wallet_moves,
        policy=load_policy(),
    )
    return {
        "scenario_id": scenario_id,
        "incident": replay.incident,
        "as_of": replay.as_of.isoformat(),
        "synthetic": True,
        "model_predictions": model_status,
        "replay": {
            "transaction_count": len(replay.transactions),
            "cashout_count": len(replay.cashouts),
            "cashout_total_bdt": sum(event.amount for event in replay.cashouts),
            "digital_balances_bdt": replay.digital_balances,
        },
        "trace": trace.to_dict(),
        "taint": taint.to_dict(),
        "recommendation": recommendation.to_dict(),
    }
