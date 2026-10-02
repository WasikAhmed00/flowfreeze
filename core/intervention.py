"""Policy-based, human-reviewed simulated intervention recommendations.

This module never changes wallet balances or calls a provider. Risk and movement
scores are inputs to policy, not actions; the returned action is a proposal for
an analyst to review in the synthetic prototype.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any, Mapping

from core.graph import TraceResult, trace_downstream
from core.simulator import ReplayResult, TransactionSimulator
from core.taint import TaintResult, calculate_proportional_taint

CENT = Decimal("0.01")
DEFAULT_POLICY = Path(__file__).with_name("policy.yaml")


@dataclass(frozen=True)
class WalletRecommendation:
    wallet_id: str
    risk_score: float | None
    next_move_probabilities: dict[str, float] | None
    balance_bdt: Decimal
    potentially_tainted_bdt: Decimal
    potentially_legitimate_bdt: Decimal
    proposed_simulated_hold_bdt: Decimal
    estimated_legitimate_value_affected_bdt: Decimal
    urgency: str
    action: str
    reasons: tuple[str, ...]
    evidence_transaction_ids: tuple[str, ...]


@dataclass(frozen=True)
class InterventionRecommendation:
    scenario_id: str
    incident_id: str
    incident_type: str
    as_of: str
    policy_version: str
    status: str
    requires_analyst_review: bool
    automatic_execution: bool
    limitations: tuple[str, ...]
    recommendations: tuple[WalletRecommendation, ...]

    def to_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


def load_policy(path: str | Path | None = None) -> dict[str, Any]:
    """Load the JSON-compatible YAML policy using the Python standard library."""
    policy_path = Path(path) if path else DEFAULT_POLICY
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read policy file {policy_path}: {exc}") from exc
    required = {
        "policy_version", "minimum_fraud_risk", "minimum_predicted_movement_probability",
        "urgent_cashout_probability", "minimum_tainted_amount_bdt",
        "maximum_simulated_hold_bdt", "wrong_recipient_dispute_requires_review",
    }
    missing = required - set(policy)
    if missing:
        raise ValueError("Policy is missing keys: " + ", ".join(sorted(missing)))
    for key in (
        "minimum_fraud_risk", "minimum_predicted_movement_probability", "urgent_cashout_probability"
    ):
        value = float(policy[key])
        if not 0 <= value <= 1:
            raise ValueError(f"Policy {key} must be between 0 and 1.")
    if Decimal(str(policy["minimum_tainted_amount_bdt"])) < 0:
        raise ValueError("minimum_tainted_amount_bdt cannot be negative.")
    if Decimal(str(policy["maximum_simulated_hold_bdt"])) < 0:
        raise ValueError("maximum_simulated_hold_bdt cannot be negative.")
    return policy


def recommend_intervention(
    replay: ReplayResult,
    taint: TaintResult,
    trace: TraceResult,
    *,
    fraud_risk: float | None = None,
    next_move_probabilities: Mapping[str, float] | None = None,
    policy: Mapping[str, Any] | None = None,
    wallet_fraud_risk: Mapping[str, float] | None = None,
    wallet_next_move_probabilities: Mapping[str, Mapping[str, float]] | None = None,
) -> InterventionRecommendation:
    """Build bounded, evidence-linked proposals without performing an action.

    Predictions can be supplied per wallet; otherwise incident-level values are
    used. Missing scores fail closed to monitoring and explicit uncertainty.
    """
    config = dict(policy or load_policy())
    _validate_probability(fraud_risk, "fraud_risk")
    if next_move_probabilities is not None:
        _validate_moves(next_move_probabilities)
    for wallet_id, value in (wallet_fraud_risk or {}).items():
        _validate_probability(value, f"wallet_fraud_risk[{wallet_id}]")
    for wallet_id, values in (wallet_next_move_probabilities or {}).items():
        _validate_moves(values)

    if replay.scenario_id != taint.scenario_id or replay.scenario_id != trace.scenario_id:
        raise ValueError("Replay, taint, and trace results must refer to the same scenario.")
    if replay.as_of != taint.as_of or replay.as_of != trace.as_of:
        raise ValueError("Replay, taint, and trace results must use the same analysis time.")

    movement_ids: dict[str, list[str]] = {}
    for movement in taint.movements:
        if movement.transaction_id != taint.reported_transaction_id:
            movement_ids.setdefault(movement.from_wallet, []).append(movement.transaction_id)
    cashout_wallets = {cashout.wallet_id: cashout.transaction_id for cashout in taint.cashouts}
    rapid_wallets: dict[str, list[str]] = {}
    for item in trace.rapid_forwards:
        rapid_wallets.setdefault(item.wallet_id, []).append(item.outgoing_transaction_id)
    fanout_wallets: dict[str, list[str]] = {}
    for item in trace.fanout_wallets:
        fanout_wallets[item.wallet_id] = list(item.transaction_ids)
    max_hold = Decimal(str(config["maximum_simulated_hold_bdt"])).quantize(CENT, rounding=ROUND_DOWN)
    minimum_taint = Decimal(str(config["minimum_tainted_amount_bdt"]))
    output: list[WalletRecommendation] = []

    for wallet in taint.wallets:
        if wallet.potentially_tainted_bdt <= 0:
            continue
        score = (wallet_fraud_risk or {}).get(wallet.wallet_id, fraud_risk)
        moves = (wallet_next_move_probabilities or {}).get(wallet.wallet_id, next_move_probabilities)
        movement_probability = (
            (moves or {}).get("forward", 0.0) + (moves or {}).get("cashout", 0.0)
        ) if moves is not None else None
        cashout_probability = (moves or {}).get("cashout") if moves is not None else None
        observed_cashout = wallet.wallet_id in cashout_wallets
        disputed = (
            "wrong_recipient" in taint.incident_type.lower()
            and bool(config["wrong_recipient_dispute_requires_review"])
        )

        reasons = [
            f"Proportional attribution estimates ৳{wallet.potentially_tainted_bdt:.2f} potentially linked to the reported transfer.",
            f"Current synthetic replay balance is ৳{wallet.balance_bdt:.2f} as of {replay.as_of.isoformat()}.",
        ]
        if score is None:
            reasons.append("Fraud risk score was not supplied; this proposal is limited to monitoring and analyst review.")
        else:
            reasons.append(f"Supplied fraud risk score: {score:.3f} (policy threshold {float(config['minimum_fraud_risk']):.3f}).")
        if moves is None:
            reasons.append("Next-move probabilities were not supplied; urgency is not model-assessed.")
        else:
            reasons.append("Supplied next-move probabilities: " + ", ".join(f"{key}={value:.3f}" for key, value in sorted(moves.items())) + ".")
        if observed_cashout:
            reasons.append("An observed cash-out is present in the replay evidence.")
        if rapid_wallets.get(wallet.wallet_id):
            reasons.append("Rapid forwarding is present in graph evidence: " + ", ".join(rapid_wallets[wallet.wallet_id]) + ".")
        if fanout_wallets.get(wallet.wallet_id):
            reasons.append("Multiple outgoing branches are present in graph evidence: " + ", ".join(fanout_wallets[wallet.wallet_id]) + ".")
        if disputed:
            reasons.append("This is a wrong-recipient dispute; policy routes it for review without a hold proposal.")

        meets_risk = score is not None and score >= float(config["minimum_fraud_risk"])
        meets_movement = movement_probability is not None and movement_probability >= float(config["minimum_predicted_movement_probability"])
        meets_taint = wallet.potentially_tainted_bdt >= minimum_taint
        action = "monitor_and_review"
        amount = Decimal("0.00")
        if disputed:
            action = "review_dispute"
        elif meets_risk and meets_taint and (meets_movement or observed_cashout):
            action = "propose_bounded_simulated_hold"
            amount = min(wallet.balance_bdt, max_hold).quantize(CENT, rounding=ROUND_DOWN)
            reasons.append("The proposed simulation amount is capped by both available balance and policy maximum; it requires analyst approval.")
        elif not meets_taint:
            reasons.append(f"Estimated taint is below policy minimum ৳{minimum_taint:.2f}.")
        elif not meets_risk:
            reasons.append("Risk is below the policy threshold or unavailable; no simulated hold is proposed.")
        elif not (meets_movement or observed_cashout):
            reasons.append("Movement evidence is below threshold or unavailable; no simulated hold is proposed.")

        legitimate_affected = max(Decimal("0.00"), amount - wallet.potentially_tainted_bdt).quantize(CENT, rounding=ROUND_DOWN)
        urgency = "urgent_review" if observed_cashout or (cashout_probability is not None and cashout_probability >= float(config["urgent_cashout_probability"])) else "standard_review"
        evidence_ids = tuple(dict.fromkeys(
            movement_ids.get(wallet.wallet_id, [])
            + rapid_wallets.get(wallet.wallet_id, [])
            + fanout_wallets.get(wallet.wallet_id, [])
            + ([cashout_wallets[wallet.wallet_id]] if observed_cashout else [])
        ))
        output.append(WalletRecommendation(
            wallet_id=wallet.wallet_id,
            risk_score=score,
            next_move_probabilities=dict(moves) if moves is not None else None,
            balance_bdt=wallet.balance_bdt,
            potentially_tainted_bdt=wallet.potentially_tainted_bdt,
            potentially_legitimate_bdt=wallet.potentially_legitimate_bdt,
            proposed_simulated_hold_bdt=amount,
            estimated_legitimate_value_affected_bdt=legitimate_affected,
            urgency=urgency,
            action=action,
            reasons=tuple(reasons),
            evidence_transaction_ids=evidence_ids,
        ))

    output.sort(key=lambda item: (item.urgency != "urgent_review", item.action == "monitor_and_review", -float(item.potentially_tainted_bdt)))
    return InterventionRecommendation(
        scenario_id=replay.scenario_id,
        incident_id=str(replay.incident["incident_id"]),
        incident_type=taint.incident_type,
        as_of=replay.as_of.isoformat(),
        policy_version=str(config["policy_version"]),
        status="recommendations_available" if output else "no_tainted_wallets_at_analysis_time",
        requires_analyst_review=True,
        automatic_execution=False,
        limitations=(
            "Synthetic-only demonstration; not connected to upay systems or customer data.",
            "Potential taint is a proportional bookkeeping estimate, not a legal ownership or fraud finding.",
            "Model scores are optional inputs and are not trained or generated by this module.",
            "Every simulated hold is a proposal; no wallet action is executed.",
        ),
        recommendations=tuple(output),
    )


def _validate_probability(value: float | None, label: str) -> None:
    if value is not None and (not 0 <= float(value) <= 1):
        raise ValueError(f"{label} must be between 0 and 1.")


def _validate_moves(values: Mapping[str, float]) -> None:
    required = {"forward", "cashout", "no_movement"}
    if set(values) != required:
        raise ValueError("Next-move probabilities must contain forward, cashout, and no_movement.")
    probabilities = [float(value) for value in values.values()]
    if any(value < 0 or value > 1 for value in probabilities):
        raise ValueError("Next-move probabilities must be between 0 and 1.")
    if abs(sum(probabilities) - 1.0) > 0.02:
        raise ValueError("Next-move probabilities must sum to 1 within 0.02.")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Create human-reviewed simulated intervention recommendations.")
    parser.add_argument("scenario_id", help="Scenario ID, such as SCN-06-FANOUT-CASHOUT-0001")
    parser.add_argument("--database", help="SQLite database path")
    parser.add_argument("--policy", help="Optional JSON-compatible YAML policy path")
    parser.add_argument("--fraud-risk", type=float, help="Incident fraud-risk score from 0 to 1")
    parser.add_argument("--p-forward", type=float, help="Next-move forward probability")
    parser.add_argument("--p-cashout", type=float, help="Next-move cashout probability")
    parser.add_argument("--p-no-movement", type=float, help="Next-move no-movement probability")
    args = parser.parse_args()
    supplied = (args.p_forward, args.p_cashout, args.p_no_movement)
    if any(value is not None for value in supplied) and not all(value is not None for value in supplied):
        parser.error("Provide all of --p-forward, --p-cashout, and --p-no-movement together.")
    moves = None if supplied[0] is None else dict(zip(("forward", "cashout", "no_movement"), supplied))
    replay = TransactionSimulator(args.database).replay(args.scenario_id)
    taint = calculate_proportional_taint(replay)
    trace = trace_downstream(replay)
    result = recommend_intervention(
        replay, taint, trace,
        fraud_risk=args.fraud_risk,
        next_move_probabilities=moves,
        policy=load_policy(args.policy),
    )
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
