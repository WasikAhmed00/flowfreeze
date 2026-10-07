"""Explainable graph-propagated risk and composite fraud intelligence scores.

This is decision support for the synthetic replay only. Graph propagation is an
interpretable one-step message-passing calculation, not a learned GNN or a fraud
finding: wallet scores combine model priors with risk from observed neighbors.
"""
from __future__ import annotations
from math import exp
from typing import Any, Mapping


def _clamp(value: float) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + exp(-max(-30.0, min(30.0, value))))


def build_intelligence(replay: Any, trace: Any, taint: Any,
                       wallet_predictions: Mapping[str, Mapping[str, Any]] | None = None,
                       prediction_window_minutes: int = 60) -> dict[str, Any]:
    """Calculate wallet-level risk components, graph propagation and forecasts."""
    predictions = wallet_predictions or {}
    wallet_taint = {row.wallet_id: row for row in taint.wallets}
    wallet_ids = list(wallet_taint)
    neighbors: dict[str, set[str]] = {wallet: set() for wallet in wallet_ids}
    for event in replay.transactions:
        if event.sender_wallet in neighbors and event.receiver_wallet in neighbors and event.sender_wallet != event.receiver_wallet:
            neighbors[event.sender_wallet].add(event.receiver_wallet)
            neighbors[event.receiver_wallet].add(event.sender_wallet)
    cashout_wallets = {row.wallet_id for row in trace.cashouts}
    rapid_wallets = {row.wallet_id for row in trace.rapid_forwards}
    fanout_wallets = {row.wallet_id for row in trace.fanout_wallets}
    raw: dict[str, dict[str, Any]] = {}
    for wallet in wallet_ids:
        model = predictions.get(wallet, {})
        ml = _clamp(model.get("fraud_risk", 0.0))
        moves = model.get("next_move_probabilities") or {}
        cashout = _clamp(moves.get("cashout", 1.0 if wallet in cashout_wallets else 0.0))
        # Transparent behavior proxy: high outgoing/incoming velocity and unusually
        # large outgoing amounts increase anomaly risk; it is not an anomaly model.
        outgoing = [e for e in replay.transactions if e.sender_wallet == wallet]
        incoming = [e for e in replay.transactions if e.receiver_wallet == wallet]
        ratio = sum(e.amount for e in outgoing) / max(sum(e.amount for e in incoming), 1.0)
        count_signal = min(1.0, len(outgoing) / 5.0)
        burst_signal = _sigmoid((ratio - 1.0) * 1.4)
        anomaly = _clamp(0.55 * burst_signal + 0.45 * count_signal)
        taint_ratio = _clamp(float(wallet_taint[wallet].potentially_tainted_ratio))
        cashout_signal = max(cashout, 0.9 if wallet in cashout_wallets else 0.0)
        suspicious_links = sum(1 for neighbor in neighbors[wallet]
                               if (predictions.get(neighbor, {}).get("fraud_risk", 0.0) >= 0.5
                                   or neighbor in cashout_wallets or neighbor in rapid_wallets or neighbor in fanout_wallets))
        connection = _clamp(suspicious_links / max(1, min(3, len(neighbors[wallet]))))
        raw[wallet] = {"ml_risk": ml, "anomaly_risk": anomaly, "taint_exposure": taint_ratio,
                       "cashout_probability": cashout_signal, "suspicious_connections": connection,
                       "neighbors": sorted(neighbors[wallet]), "suspicious_neighbor_count": suspicious_links,
                       "outgoing_count": len(outgoing), "velocity_ratio": round(ratio, 3), "moves": moves}
    # Two deterministic iterations of risk propagation over observed wallet links.
    # Model predictions seed the graph; observed rapid forwards/cashouts contribute
    # evidence but never trigger an action.
    scores = {wallet: row["ml_risk"] for wallet, row in raw.items()}
    for _ in range(2):
        updated = {}
        for wallet, row in raw.items():
            linked = [scores[n] for n in row["neighbors"]]
            structural = (sum(linked) / len(linked)) if linked else 0.0
            evidence = 0.15 * (wallet in rapid_wallets) + 0.2 * (wallet in fanout_wallets) + 0.25 * (wallet in cashout_wallets)
            updated[wallet] = _clamp(0.72 * row["ml_risk"] + 0.23 * structural + evidence)
        scores = updated
    output = {}
    weights = {"ml_risk": .25, "graph_risk": .20, "anomaly_risk": .15,
               "taint_exposure": .15, "cashout_probability": .15, "suspicious_connections": .10}
    for wallet, row in raw.items():
        graph = scores[wallet]
        components = {**{key: row[key] for key in weights if key != "graph_risk"}, "graph_risk": graph}
        score = round(100 * sum(components[key] * weight for key, weight in weights.items()))
        moves = row["moves"]
        selected = max(moves, key=moves.get) if moves else "insufficient_model_data"
        prob = float(moves.get(selected, 0.0)) if moves else 0.0
        observed = [e for e in replay.transactions if e.sender_wallet == wallet]
        intervals = [(b.timestamp-a.timestamp).total_seconds()/60 for a,b in zip(observed, observed[1:]) if b.timestamp > a.timestamp]
        eta = max(1, round(sorted(intervals)[len(intervals)//2])) if intervals else max(1, int(prediction_window_minutes * (1-prob*.5)))
        explanation = []
        if row["ml_risk"] >= .5: explanation.append("elevated trained-model risk prior")
        if graph > row["ml_risk"] + .05: explanation.append(f"risk propagated from {len(row['neighbors'])} observed counterparty link(s)")
        if row["anomaly_risk"] >= .55: explanation.append(f"outflow/inflow ratio {row['velocity_ratio']:.2f} and {row['outgoing_count']} outgoing events")
        if row["taint_exposure"] > 0: explanation.append(f"{row['taint_exposure']:.0%} proportional taint exposure")
        if row["cashout_probability"] >= .45: explanation.append("cash-out movement is likely or already observed")
        if not explanation: explanation.append("no strong signal in the available synthetic snapshot")
        output[wallet] = {
            "fraud_score": score, "components": {key: round(value*100, 1) for key,value in components.items()},
            "graph_risk": round(graph, 4), "graph_explanation": explanation,
            "prediction": {"next_movement": selected, "probability": round(prob, 4),
                "estimated_minutes": eta, "cashout_likelihood": round(row["cashout_probability"], 4),
                "confidence": round(max(0.0, min(1.0, prob * (0.65 + .35 * abs(prob - .5) * 2))), 4),
                "explanation": explanation},
            "suspicious_wallet_connections": row["neighbors"],
        }
    return {"method": "two-iteration explainable graph risk propagation", "score_weights": weights,
            "wallets": output, "interpretation": "Synthetic decision-support score; not a legal finding or automatic action."}


def simulate_what_if(intelligence: Mapping[str, Any], taint: Any, *, action: str,
                     source_wallet: str | None = None, target_wallet: str | None = None,
                     amount: float = 0.0) -> dict[str, Any]:
    """Estimate a local counterfactual without mutating replay or database state."""
    wallets = intelligence["wallets"]
    if action not in {"transfer", "cashout", "intervention"}:
        raise ValueError("action must be transfer, cashout, or intervention")
    if action == "transfer" and (source_wallet not in wallets or target_wallet not in wallets):
        raise ValueError("source_wallet and target_wallet must identify wallets in this scenario")
    if action == "cashout" and source_wallet not in wallets:
        raise ValueError("source_wallet must identify a wallet in this scenario")
    if amount < 0:
        raise ValueError("amount cannot be negative")
    before_score = max((row["fraud_score"] for row in wallets.values()), default=0)
    before_taint = float(taint.remaining_potentially_tainted_bdt)
    before_prediction = max(wallets, key=lambda w: wallets[w]["prediction"]["cashout_likelihood"]) if wallets else None
    impact = min(20, max(3, round(amount / 1000))) if amount else 8
    after_score = max(0, before_score - impact) if action == "intervention" else min(100, before_score + impact)
    after_taint = max(0.0, before_taint - min(amount, before_taint)) if action == "intervention" else min(before_taint + amount * .25, before_taint + amount)
    after_prediction = target_wallet if action == "transfer" else (source_wallet if action == "cashout" else before_prediction)
    return {"action": action, "source_wallet": source_wallet, "target_wallet": target_wallet,
            "amount_bdt": round(amount, 2), "baseline": {"risk": before_score, "taint_bdt": round(before_taint,2), "predicted_wallet": before_prediction},
            "counterfactual": {"risk": after_score, "taint_bdt": round(after_taint,2), "predicted_wallet": after_prediction},
            "delta": {"risk": after_score-before_score, "taint_bdt": round(after_taint-before_taint,2)},
            "explanation": "Deterministic scenario estimate based on score/taint signals; no replay ledger, wallet, or decision record was changed.",
            "synthetic": True, "ledger_changed": False}
