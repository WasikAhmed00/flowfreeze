"""Build decision-time wallet features from events visible at analysis_at.

Identifiers, ground-truth fields, split labels, and post-analysis events are
retained only as row metadata/targets and are excluded from FEATURE_COLUMNS.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import pandas as pd

from data_generator.config import DEFAULT_DATA_DIR

NUMERIC_FEATURES = [
    "account_age_days", "opening_balance_bdt", "profile_average_transaction_bdt",
    "profile_frequency_per_day", "reported_amount_bdt", "amount_to_profile_average_ratio",
    "report_to_analysis_seconds", "reported_sender", "reported_recipient",
    "observed_incoming_count", "observed_outgoing_count", "observed_transaction_count",
    "observed_incoming_amount_bdt", "observed_outgoing_amount_bdt", "observed_net_flow_bdt",
    "observed_average_outgoing_bdt", "observed_max_outgoing_bdt", "observed_cashout_count",
    "post_report_incoming_count", "post_report_outgoing_count", "post_report_outgoing_amount_bdt",
    "post_report_cashout_count", "merchant_payment_count", "distinct_counterparties",
    "graph_hops_from_reported_recipient", "reachable_from_reported_recipient",
]
CATEGORICAL_FEATURES = ["customer_type", "normal_active_hours", "usual_transaction_types", "incident_type"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
IDENTIFIER_COLUMNS = ["scenario_id", "wallet_id", "split"]
TARGET_COLUMNS = ["fraud_flag", "expected_next_action"]


def _reachability(visible: list[dict[str, Any]], root: str) -> dict[str, int]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for event in visible:
        adjacency[str(event["sender_wallet"])].append(str(event["receiver_wallet"]))
    hops = {root: 0}
    queue = deque([root])
    while queue:
        current = queue.popleft()
        for receiver in adjacency[current]:
            if receiver not in hops:
                hops[receiver] = hops[current] + 1
                queue.append(receiver)
    return hops


def build_decision_features(data_dir: str | Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Build inference-time rows from profiles and visible transactions only.

    This function intentionally does not read ground_truth.csv. It is the same
    feature path used by the training table and online scenario prediction.
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
    transactions_by_scenario = {
        scenario_id: group.to_dict("records")
        for scenario_id, group in transactions.groupby("scenario_id", sort=False)
    }
    rows: list[dict[str, Any]] = []

    for scenario_id, group in wallets[wallets["customer_type"] != "cash_destination"].groupby("scenario_id", sort=False):
        incident = incident_lookup.get(scenario_id)
        if incident is None:
            raise ValueError(f"Wallet profile references unknown scenario {scenario_id!r}.")
        all_events = transactions_by_scenario.get(scenario_id, [])
        cutoff = incident["analysis_at"]
        reported_at = incident["reported_at"]
        visible = [event for event in all_events if event["timestamp"] <= cutoff]
        reported_id = str(incident["reported_transaction_id"])
        reported = next((event for event in visible if str(event["transaction_id"]) == reported_id), None)
        if reported is None:
            raise ValueError(f"Reported transaction {reported_id!r} is not visible at analysis_at.")
        root = str(reported["receiver_wallet"])
        hops = _reachability(visible, root)

        for profile in group.to_dict("records"):
            wallet_id = str(profile["wallet_id"])
            incoming = [event for event in visible if str(event["receiver_wallet"]) == wallet_id]
            outgoing = [event for event in visible if str(event["sender_wallet"]) == wallet_id]
            pre_report_in = [event for event in incoming if event["timestamp"] < reported_at]
            pre_report_out = [event for event in outgoing if event["timestamp"] < reported_at]
            post_report_in = [event for event in incoming if event["timestamp"] >= reported_at]
            post_report_out = [event for event in outgoing if event["timestamp"] >= reported_at]
            amount = float(incident["reported_amount"])
            profile_average = float(profile["average_transaction_amount"] or 0)
            counterparties = {
                str(event["sender_wallet"] if event in incoming else event["receiver_wallet"])
                for event in incoming + outgoing
            }
            outgoing_amounts = [float(event["amount"]) for event in outgoing]
            post_cashouts = [event for event in post_report_out if str(event["transaction_type"]) == "cashout"]
            cashouts = [event for event in outgoing if str(event["transaction_type"]) == "cashout"]
            row: dict[str, Any] = {
                "scenario_id": scenario_id,
                "wallet_id": wallet_id,
                "account_age_days": float(profile["account_age"]),
                "opening_balance_bdt": float(profile["baseline_balance"]),
                "profile_average_transaction_bdt": profile_average,
                "profile_frequency_per_day": float(profile["transaction_frequency"]),
                "reported_amount_bdt": amount,
                "amount_to_profile_average_ratio": amount / max(profile_average, 1.0),
                "report_to_analysis_seconds": max(0.0, (cutoff - reported_at).total_seconds()),
                "reported_sender": int(wallet_id == str(reported["sender_wallet"])),
                "reported_recipient": int(wallet_id == root),
                "observed_incoming_count": len(incoming),
                "observed_outgoing_count": len(outgoing),
                "observed_transaction_count": len(incoming) + len(outgoing),
                "observed_incoming_amount_bdt": sum(float(event["amount"]) for event in incoming),
                "observed_outgoing_amount_bdt": sum(outgoing_amounts),
                "observed_net_flow_bdt": sum(float(event["amount"]) for event in incoming) - sum(outgoing_amounts),
                "observed_average_outgoing_bdt": sum(outgoing_amounts) / len(outgoing_amounts) if outgoing_amounts else 0.0,
                "observed_max_outgoing_bdt": max(outgoing_amounts, default=0.0),
                "observed_cashout_count": len(cashouts),
                "post_report_incoming_count": len(post_report_in),
                "post_report_outgoing_count": len(post_report_out),
                "post_report_outgoing_amount_bdt": sum(float(event["amount"]) for event in post_report_out),
                "post_report_cashout_count": len(post_cashouts),
                "merchant_payment_count": sum(str(event["transaction_type"]) == "merchant_payment" for event in incoming + outgoing),
                "distinct_counterparties": len(counterparties),
                "graph_hops_from_reported_recipient": float(hops.get(wallet_id, -1)),
                "reachable_from_reported_recipient": int(wallet_id in hops),
                "customer_type": str(profile["customer_type"]),
                "normal_active_hours": str(profile["normal_active_hours"]),
                "usual_transaction_types": str(profile["usual_transaction_types"]),
                "incident_type": str(incident["incident_type"]),
            }
            rows.append(row)

    table = pd.DataFrame(rows)
    missing_features = set(FEATURE_COLUMNS) - set(table.columns)
    if missing_features:
        raise ValueError("Feature generation omitted: " + ", ".join(sorted(missing_features)))
    if table[FEATURE_COLUMNS].isna().all(axis=1).any():
        raise ValueError("Some wallet rows have no usable decision-time features.")
    return table


def build_feature_table(data_dir: str | Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Join decision-time features to offline-only labels/split metadata."""
    folder = Path(data_dir)
    truth = pd.read_csv(folder / "ground_truth.csv", keep_default_na=False)
    if truth.duplicated(["scenario_id", "wallet_id"]).any():
        raise ValueError("Ground truth has duplicate wallet rows for a scenario.")
    features = build_decision_features(folder)
    label_columns = ["scenario_id", "wallet_id", "split", "fraud_flag", "expected_next_action"]
    table = features.merge(
        truth[label_columns], on=["scenario_id", "wallet_id"], how="left", validate="one_to_one",
    )
    if table["split"].isna().any() or table[TARGET_COLUMNS].isna().any(axis=None):
        raise ValueError("Every inference wallet row must match one ground-truth row for offline training.")
    table["fraud_flag"] = table["fraud_flag"].astype(int)
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description="Build leakage-aware decision-time FlowFreeze features.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args()
    table = build_feature_table(args.data_dir)
    print({
        "rows": len(table),
        "scenarios": table["scenario_id"].nunique(),
        "features": len(FEATURE_COLUMNS),
        "split_rows": table.groupby("split").size().to_dict(),
        "fraud_labels": table["fraud_flag"].value_counts().to_dict(),
        "next_move_labels": table["expected_next_action"].value_counts().to_dict(),
    })


if __name__ == "__main__":
    main()
