"""Compose existing FlowFreeze analysis layers for backend/API consumers."""

from __future__ import annotations

from typing import Mapping

from core.graph import trace_downstream
from core.intervention import load_policy, recommend_intervention
from core.simulator import ReplayResult, TransactionSimulator
from core.taint import calculate_proportional_taint


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
    recommendation = recommend_intervention(
        replay,
        taint,
        trace,
        fraud_risk=fraud_risk,
        next_move_probabilities=next_move_probabilities,
        policy=load_policy(),
    )
    return {
        "scenario_id": scenario_id,
        "incident": replay.incident,
        "as_of": replay.as_of.isoformat(),
        "synthetic": True,
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
