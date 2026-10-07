"""Compose existing FlowFreeze analysis layers for backend/API consumers."""

from __future__ import annotations

from typing import Any, Mapping

from core.graph import trace_downstream
from core.intervention import load_policy, recommend_intervention
from core.simulator import ReplayResult, TransactionSimulator
from core.taint import calculate_proportional_taint
from core.intelligence import build_intelligence
from ml.predict import predict_scenario


def analyze_live_transaction(connection, transaction: Mapping[str, Any]) -> dict:
    """Score one synthetic live event through the incremental analysis pipeline.

    Scenario replay remains the source of full balance-proportional taint. The
    real-time adapter uses bounded graph context and explicitly labeled
    synthetic heuristic outputs so it can score events without rebuilding a
    complete incident replay for every request.
    """
    from backend.streaming import process_transaction

    return process_transaction(connection, dict(transaction))


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
                if item.get("fraud_risk") is not None
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
                "fraud_model_sample_rows": predictions.get("fraud_model_sample_rows"),
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
    intelligence_predictions = {
        wallet: {"fraud_risk": risk, "next_move_probabilities": (wallet_moves or {}).get(wallet, {})}
        for wallet, risk in (wallet_risk or {}).items()
    }
    if not intelligence_predictions and (fraud_risk is not None or next_move_probabilities is not None):
        illustrative_moves = dict(next_move_probabilities or {})
        intelligence_predictions = {
            wallet.wallet_id: {"fraud_risk": float(fraud_risk or 0.0),
                               "next_move_probabilities": illustrative_moves}
            for wallet in taint.wallets
        }
    intelligence = build_intelligence(
        replay, trace, taint,
        intelligence_predictions,
        prediction_window_minutes=int(model_status.get("next_move_window_minutes", 60)),
    )
    recommendation_payload = recommendation.to_dict()
    for item in recommendation_payload["recommendations"]:
        details = intelligence["wallets"].get(item["wallet_id"])
        if details:
            item["fraud_intelligence_score"] = details["fraud_score"]
            item["expected_risk_reduction_points"] = round(
                details["fraud_score"] * min(1.0, float(item["proposed_simulated_hold_bdt"]) /
                max(1.0, float(item["balance_bdt"]))) * 0.5, 1)
            item["recommendation_reasons"] = list(item["reasons"])
    return {
        "scenario_id": scenario_id,
        "incident": replay.incident,
        "as_of": replay.as_of.isoformat(),
        "synthetic": True,
        "model_predictions": model_status,
        "intelligence": intelligence,
        "replay": {
            "transaction_count": len(replay.transactions),
            "cashout_count": len(replay.cashouts),
            "cashout_total_bdt": sum(event.amount for event in replay.cashouts),
            "digital_balances_bdt": replay.digital_balances,
        },
        "trace": trace.to_dict(),
        "taint": taint.to_dict(),
        "recommendation": recommendation_payload,
    }
