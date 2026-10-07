from __future__ import annotations

from core.graph import trace_downstream
from core.intelligence import build_intelligence, simulate_what_if
from core.simulator import TransactionSimulator
from core.taint import calculate_proportional_taint


def test_intelligence_exposes_explainable_scores_and_forecast(generated_fixture, fanout_scenario):
    replay = TransactionSimulator(generated_fixture["database"]).replay(fanout_scenario)
    trace = trace_downstream(replay)
    taint = calculate_proportional_taint(replay)
    inputs = {wallet.wallet_id: {"fraud_risk": .72,
             "next_move_probabilities": {"forward": .45, "cashout": .4, "no_movement": .15}}
              for wallet in taint.wallets}
    result = build_intelligence(replay, trace, taint, inputs, prediction_window_minutes=30)
    assert result["method"].startswith("two-iteration explainable graph")
    assert result["wallets"]
    for wallet in result["wallets"].values():
        assert 0 <= wallet["fraud_score"] <= 100
        assert set(wallet["components"]) == {"ml_risk", "graph_risk", "anomaly_risk", "taint_exposure", "cashout_probability", "suspicious_connections"}
        assert wallet["prediction"]["next_movement"] in {"forward", "cashout", "no_movement"}
        assert 0 <= wallet["prediction"]["confidence"] <= 1
        assert wallet["graph_explanation"]


def test_what_if_is_counterfactual_and_validates_wallets(generated_fixture, fanout_scenario):
    replay = TransactionSimulator(generated_fixture["database"]).replay(fanout_scenario)
    trace = trace_downstream(replay)
    taint = calculate_proportional_taint(replay)
    intelligence = build_intelligence(replay, trace, taint)
    wallets = list(intelligence["wallets"])
    before = dict(replay.final_balances)
    result = simulate_what_if(intelligence, taint, action="transfer",
                              source_wallet=wallets[0], target_wallet=wallets[-1], amount=900)
    assert result["ledger_changed"] is False
    assert result["counterfactual"]["predicted_wallet"] == wallets[-1]
    assert result["delta"]["risk"] >= 0
    assert replay.final_balances == before
    try:
        simulate_what_if(intelligence, taint, action="transfer", source_wallet="missing", target_wallet=wallets[-1])
    except ValueError as exc:
        assert "identify wallets" in str(exc)
    else:
        raise AssertionError("Unknown wallet should be rejected")
