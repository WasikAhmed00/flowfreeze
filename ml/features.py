"""Build leakage-aware, decision-time wallet behavior features."""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Any
import pandas as pd
from data_generator.config import DEFAULT_DATA_DIR

NUMERIC_FEATURES = [
    "reported_amount_bdt", "amount_to_prior_average_ratio", "report_to_analysis_seconds",
    "observed_incoming_count", "observed_outgoing_count", "observed_transaction_count",
    "observed_incoming_amount_bdt", "observed_outgoing_amount_bdt", "observed_net_flow_bdt",
    "observed_average_outgoing_bdt", "observed_max_outgoing_bdt", "observed_cashout_count",
    "merchant_payment_count", "distinct_counterparties", "prior_relationship_count",
    "prior_relationship_amount_bdt", "prior_active_days", "incoming_outgoing_count_ratio",
]
CATEGORICAL_FEATURES = ["normal_active_hours", "usual_transaction_types"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
IDENTIFIER_COLUMNS = ["scenario_id", "wallet_id", "split"]
TARGET_COLUMNS = ["fraud_flag", "expected_next_action"]


def build_decision_features(data_dir: str | Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Build rows from profiles and events visible by ``analysis_at`` only.

    Graph reachability and incident-role flags stay in the evidence layer; they
    are intentionally not classifier features.
    """
    folder = Path(data_dir)
    incidents = pd.read_csv(folder / "incidents.csv", dtype={"scenario_id": str})
    wallets = pd.read_csv(folder / "wallets.csv", keep_default_na=False)
    transactions = pd.read_csv(folder / "transactions.csv", keep_default_na=False)
    for frame, column in ((incidents, "analysis_at"), (incidents, "reported_at"), (transactions, "timestamp")):
        frame[column] = pd.to_datetime(frame[column], format="mixed", utc=True, errors="raise")
    if incidents["scenario_id"].duplicated().any():
        raise ValueError("Expected one incident row per scenario_id.")
    incident_lookup = incidents.set_index("scenario_id").to_dict("index")
    transactions = transactions.sort_values(["timestamp", "transaction_id"])
    by_scenario = {sid: group.to_dict("records") for sid, group in transactions.groupby("scenario_id", sort=False)}
    rows: list[dict[str, Any]] = []
    for scenario_id, group in wallets[wallets["customer_type"] != "cash_destination"].groupby("scenario_id", sort=False):
        incident = incident_lookup.get(scenario_id)
        if incident is None:
            raise ValueError(f"Wallet profile references unknown scenario {scenario_id!r}.")
        cutoff, reported_at = incident["analysis_at"], incident["reported_at"]
        visible = [event for event in by_scenario.get(scenario_id, []) if event["timestamp"] <= cutoff]
        reported_id = str(incident["reported_transaction_id"])
        if not any(str(event["transaction_id"]) == reported_id for event in visible):
            raise ValueError(f"Reported transaction {reported_id!r} is not visible at analysis_at.")
        for profile in group.to_dict("records"):
            wallet_id = str(profile["wallet_id"])
            incoming = [e for e in visible if str(e["receiver_wallet"]) == wallet_id]
            outgoing = [e for e in visible if str(e["sender_wallet"]) == wallet_id]
            prior_in = [e for e in incoming if e["timestamp"] < reported_at]
            prior_out = [e for e in outgoing if e["timestamp"] < reported_at]
            prior = prior_in + prior_out
            outgoing_amounts = [float(e["amount"]) for e in outgoing]
            prior_amounts = [float(e["amount"]) for e in prior]
            counterparties = {str(e["sender_wallet"] if e in incoming else e["receiver_wallet"]) for e in incoming + outgoing}
            prior_counterparties = {str(e["sender_wallet"] if e in prior_in else e["receiver_wallet"]) for e in prior}
            prior_average = sum(prior_amounts) / len(prior_amounts) if prior_amounts else 0.0
            rows.append({
                "scenario_id": scenario_id, "wallet_id": wallet_id,
                "reported_amount_bdt": float(incident["reported_amount"]),
                "amount_to_prior_average_ratio": float(incident["reported_amount"]) / max(prior_average, 1.0),
                "report_to_analysis_seconds": max(0.0, (cutoff - reported_at).total_seconds()),
                "observed_incoming_count": len(incoming), "observed_outgoing_count": len(outgoing),
                "observed_transaction_count": len(incoming) + len(outgoing),
                "observed_incoming_amount_bdt": sum(float(e["amount"]) for e in incoming),
                "observed_outgoing_amount_bdt": sum(outgoing_amounts),
                "observed_net_flow_bdt": sum(float(e["amount"]) for e in incoming) - sum(outgoing_amounts),
                "observed_average_outgoing_bdt": sum(outgoing_amounts) / len(outgoing_amounts) if outgoing_amounts else 0.0,
                "observed_max_outgoing_bdt": max(outgoing_amounts, default=0.0),
                "observed_cashout_count": sum(str(e["transaction_type"]) == "cashout" for e in outgoing),
                "merchant_payment_count": sum(str(e["transaction_type"]) == "merchant_payment" for e in incoming + outgoing),
                "distinct_counterparties": len(counterparties), "prior_relationship_count": len(prior_counterparties),
                "prior_relationship_amount_bdt": sum(prior_amounts),
                "prior_active_days": len({e["timestamp"].date() for e in prior}),
                "incoming_outgoing_count_ratio": len(incoming) / max(len(outgoing), 1),
                "normal_active_hours": str(profile["normal_active_hours"]),
                "usual_transaction_types": str(profile["usual_transaction_types"]),
            })
    table = pd.DataFrame(rows)
    missing = set(FEATURE_COLUMNS) - set(table.columns)
    if missing:
        raise ValueError("Feature generation omitted: " + ", ".join(sorted(missing)))
    if table[FEATURE_COLUMNS].isna().all(axis=1).any():
        raise ValueError("Some wallet rows have no usable decision-time features.")
    return table


def build_feature_table(data_dir: str | Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    folder = Path(data_dir)
    truth = pd.read_csv(folder / "ground_truth.csv", keep_default_na=False)
    if truth.duplicated(["scenario_id", "wallet_id"]).any():
        raise ValueError("Ground truth has duplicate wallet rows for a scenario.")
    table = build_decision_features(folder).merge(
        truth[["scenario_id", "scenario_type", "wallet_id", "split", "fraud_flag", "expected_next_action"]],
        on=["scenario_id", "wallet_id"], how="left", validate="one_to_one")
    if table["split"].isna().any() or table[TARGET_COLUMNS].isna().any(axis=None):
        raise ValueError("Every inference wallet row must match one ground-truth row for offline training.")
    table["fraud_flag"] = table["fraud_flag"].astype(int)
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description="Build leakage-aware decision-time FlowFreeze features.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args()
    table = build_feature_table(args.data_dir)
    print({"rows": len(table), "scenarios": table["scenario_id"].nunique(), "features": len(FEATURE_COLUMNS), "split_rows": table.groupby("split").size().to_dict()})


if __name__ == "__main__":
    main()
