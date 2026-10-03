from __future__ import annotations

from core.graph import trace_downstream
from core.intervention import recommend_intervention
from core.simulator import TransactionSimulator
from core.taint import calculate_proportional_taint
from ml.predict import predict_scenario


def test_flowfreeze_pipeline(trained_fixture, fanout_scenario):
    prediction = predict_scenario(
        fanout_scenario,
        data_dir=trained_fixture["data_dir"],
        artifact_dir=trained_fixture["artifact_dir"],
    )
    replay = TransactionSimulator(trained_fixture["database"]).replay(fanout_scenario)
    trace = trace_downstream(replay)
    taint = calculate_proportional_taint(replay)
    recommendation = recommend_intervention(
        replay,
        taint,
        trace,
        wallet_fraud_risk={
            wallet_id: item["fraud_risk"]
            for wallet_id, item in prediction["wallet_predictions"].items()
        },
        wallet_next_move_probabilities={
            wallet_id: item["next_move_probabilities"]
            for wallet_id, item in prediction["wallet_predictions"].items()
        },
    )

    result = {
        "incident": replay.incident,
        "feature_rows": len(prediction["wallet_predictions"]),
        "fraud_prediction": prediction["wallet_predictions"],
        "next_move_prediction": prediction["wallet_predictions"],
        "graph_trace": trace.to_dict(),
        "taint": taint.to_dict(),
        "recommendation": recommendation.to_dict(),
    }

    assert result["incident"]["scenario_id"] == fanout_scenario
    assert result["feature_rows"] > 0
    assert all("fraud_risk" in row for row in result["fraud_prediction"].values())
    assert all("next_move_probabilities" in row for row in result["next_move_prediction"].values())
    assert result["taint"]["reported_amount_bdt"]
    assert result["recommendation"]["requires_analyst_review"] is True
    assert result["recommendation"]["automatic_execution"] is False
