"""End-to-end synthetic comparison against a direct-recipient-only baseline.

The experiment runs both strategies on the same held-out incident cases and
uses generated remaining-taint labels only to score hypothetical proposals.
It never executes an intervention or changes a balance.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from backend.db import DEFAULT_DATABASE_PATH
from core.graph import trace_downstream
from core.intervention import load_policy, recommend_intervention
from core.simulator import TransactionSimulator
from core.taint import calculate_proportional_taint
from data_generator.config import DEFAULT_DATA_DIR
from ml.calibration import apply_multiclass_calibrators
from ml.features import FEATURE_COLUMNS, build_decision_features
from ml.train import DEFAULT_ARTIFACT_DIR

CENT = Decimal("0.01")


def _evaluate_strategy(
    recommendations: list[Any],
    eligible_wallets: set[str],
    truth_by_wallet: dict[str, Decimal],
) -> dict[str, Decimal | int]:
    proposals = [
        item for item in recommendations
        if item.wallet_id in eligible_wallets and item.action == "propose_bounded_simulated_hold"
    ]
    proposed = sum((item.proposed_simulated_hold_bdt for item in proposals), Decimal("0.00"))
    preserved = sum((min(item.proposed_simulated_hold_bdt, truth_by_wallet.get(item.wallet_id, Decimal("0.00"))) for item in proposals), Decimal("0.00"))
    affected = max(Decimal("0.00"), proposed - preserved)
    return {
        "cases_with_proposal": int(bool(proposals)),
        "wallets_with_proposal": len(proposals),
        "proposed_hold_bdt": proposed.quantize(CENT),
        "estimated_tainted_value_preserved_bdt": preserved.quantize(CENT),
        "estimated_legitimate_value_affected_bdt": affected.quantize(CENT),
    }


def _sum_strategy(records: list[dict[str, Any]], name: str) -> dict[str, Any]:
    keys = (
        "cases_with_proposal", "wallets_with_proposal", "proposed_hold_bdt",
        "estimated_tainted_value_preserved_bdt", "estimated_legitimate_value_affected_bdt",
    )
    summed: dict[str, Any] = {}
    for key in keys:
        values = [record[name][key] for record in records]
        summed[key] = sum(values, Decimal("0.00")) if values and isinstance(values[0], Decimal) else sum(values)
    count = len(records)
    summed["case_count"] = count
    summed["case_proposal_rate"] = round(summed["cases_with_proposal"] / count, 4) if count else 0.0
    return summed


def run_end_to_end_evaluation(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    output_path: str | Path | None = None,
    *,
    split: str = "test",
) -> dict[str, Any]:
    """Compare policy proposals for traced wallets vs. the direct recipient.

    Remaining ground-truth taint measures hypothetical value availability at
    the incident analysis time. Preserved value assumes a proposal instantly
    prevents that held portion from moving; it is not an observed outcome.
    """
    import joblib

    folder = Path(data_dir)
    features = build_decision_features(folder)
    raw_truth = pd.read_csv(folder / "ground_truth.csv", keep_default_na=False)
    selected_truth = raw_truth[raw_truth["split"] == split]
    if selected_truth.empty:
        raise ValueError(f"No cases were assigned to the requested {split!r} split.")
    scenario_ids = set(selected_truth["scenario_id"].astype(str))
    selected_features = features[features["scenario_id"].isin(scenario_ids)]
    truth: dict[str, dict[str, Decimal]] = {}
    for row in selected_truth[["scenario_id", "wallet_id", "tainted_amount"]].to_dict("records"):
        truth.setdefault(str(row["scenario_id"]), {})[str(row["wallet_id"])] = Decimal(str(row["tainted_amount"])).quantize(CENT)

    incidents = pd.read_csv(folder / "incidents.csv", keep_default_na=False)
    incident_lookup = incidents.set_index("scenario_id").to_dict("index")
    fraud_model = joblib.load(Path(artifact_dir) / "fraud_model.joblib")
    movement_model = joblib.load(Path(artifact_dir) / "next_move_model.joblib")
    policy = load_policy()
    records: list[dict[str, Any]] = []
    case_times: list[float] = []

    for scenario_id, scenario_features in selected_features.groupby("scenario_id", sort=True):
        scenario_id = str(scenario_id)
        started = time.perf_counter()
        x = scenario_features[FEATURE_COLUMNS]
        fraud_classes = list(fraud_model["pipeline"].classes_)
        fraud_probs = fraud_model["pipeline"].predict_proba(x)[:, fraud_classes.index(1)]
        movement_classes = list(movement_model["pipeline"].classes_)
        movement_probs = apply_multiclass_calibrators(
            movement_model["pipeline"].predict_proba(x), movement_classes, movement_model["calibrators"],
        )
        risk_by_wallet = dict(zip(scenario_features["wallet_id"].astype(str), fraud_probs.tolist()))
        movement_by_wallet = {
            str(wallet_id): {label: float(probs[index]) for index, label in enumerate(movement_classes)}
            for wallet_id, probs in zip(scenario_features["wallet_id"], movement_probs)
        }

        replay = TransactionSimulator(database_path).replay(scenario_id)
        trace = trace_downstream(replay)
        taint = calculate_proportional_taint(replay)
        recommendation = recommend_intervention(
            replay, taint, trace, policy=policy,
            wallet_fraud_risk=risk_by_wallet,
            wallet_next_move_probabilities=movement_by_wallet,
        )
        reported_id = str(incident_lookup[scenario_id]["reported_transaction_id"])
        reported = next(event for event in replay.transactions if event.transaction_id == reported_id)
        direct_recipient = reported.receiver_wallet
        full_metrics = _evaluate_strategy(recommendation.recommendations, {wallet.wallet_id for wallet in taint.wallets}, truth.get(scenario_id, {}))
        baseline_metrics = _evaluate_strategy(recommendation.recommendations, {direct_recipient}, truth.get(scenario_id, {}))
        elapsed_ms = (time.perf_counter() - started) * 1000
        case_times.append(elapsed_ms)
        records.append({
            "scenario_id": scenario_id,
            "scenario_type": str(incident_lookup[scenario_id]["scenario_type"]),
            "downstream_wallets_found": len(trace.downstream_wallet_ids),
            "ground_truth_tainted_wallets_downstream": sum(
                1 for wallet_id, amount in truth.get(scenario_id, {}).items()
                if amount > 0 and wallet_id != direct_recipient and wallet_id in trace.downstream_wallet_ids
            ),
            "recommendation_time_ms": elapsed_ms,
            "direct_recipient_only": baseline_metrics,
            "flowfreeze_network": full_metrics,
        })

    baseline = _sum_strategy(records, "direct_recipient_only")
    network = _sum_strategy(records, "flowfreeze_network")
    family_metrics: dict[str, Any] = {}
    for family in sorted({row["scenario_type"] for row in records}):
        subset = [row for row in records if row["scenario_type"] == family]
        family_metrics[family] = {
            "case_count": len(subset),
            "direct_recipient_only": _sum_strategy(subset, "direct_recipient_only"),
            "flowfreeze_network": _sum_strategy(subset, "flowfreeze_network"),
        }
    differences = {
        key: network[key] - baseline[key]
        for key in ("estimated_tainted_value_preserved_bdt", "estimated_legitimate_value_affected_bdt", "proposed_hold_bdt")
    }
    result: dict[str, Any] = {
        "synthetic_only": True,
        "experiment": "direct_recipient_only_vs_policy_scored_traced_wallets",
        "policy_version": policy["policy_version"],
        "split": split,
        "scenario_cases": len(records),
        "seed": json.loads((folder / "generation_metadata.json").read_text(encoding="utf-8")).get("seed"),
        "scope": "Both strategies use the same held-out cases, decision-time model scores, policy thresholds, taint estimates, analysis snapshots, and per-wallet hold caps. The baseline may propose only for the reported transaction's direct recipient; FlowFreeze may propose for any positively attributed wallet.",
        "outcome_assumptions": [
            "Hypothetical proposals are assumed to take effect immediately at analysis_at.",
            "Estimated tainted value preserved is min(proposed amount, generator's remaining tainted_amount label at analysis_at).",
            "Estimated legitimate value affected is the remainder of the proposed amount after that label-based taint amount.",
            "These are generated-data counterfactual estimates, not observed prevented losses or customer impact.",
        ],
        "direct_recipient_only": baseline,
        "flowfreeze_network": network,
        "network_minus_baseline": differences,
        "tracing": {
            "average_downstream_wallets_found_per_case": round(statistics.mean(row["downstream_wallets_found"] for row in records), 3),
            "total_downstream_wallets_found_across_cases": sum(row["downstream_wallets_found"] for row in records),
            "ground_truth_tainted_downstream_wallets_found": sum(row["ground_truth_tainted_wallets_downstream"] for row in records),
        },
        "timing": {
            "measurement": "Per-case local CPU wall time for batched-row model inference, replay, graph, taint, and policy recommendation; excludes process startup and initial feature-table/model loading.",
            "median_recommendation_ms": round(statistics.median(case_times), 3),
            "p95_recommendation_ms": round(float(pd.Series(case_times).quantile(0.95)), 3),
        },
        "by_scenario_family": family_metrics,
        "limitation": "Same-family synthetic test split only; do not present as upay BD production performance. See docs/MODEL_CARD.md and docs/RESPONSIBLE_AI.md.",
    }
    destination = Path(output_path) if output_path else Path(artifact_dir) / "end_to_end_metrics.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, default=lambda item: f"{item:.2f}" if isinstance(item, Decimal) else item, allow_nan=False), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare FlowFreeze with a direct-recipient-only baseline on the same synthetic cases.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--split", choices=("train", "validation", "test"), default="test")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(run_end_to_end_evaluation(args.data_dir, args.artifact_dir, args.database, args.output, split=args.split), indent=2, default=str))


if __name__ == "__main__":
    main()
