"""Load saved models and predict wallet risk for a FlowFreeze scenario."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from data_generator.config import DEFAULT_DATA_DIR
from ml.calibration import apply_multiclass_calibrators
from ml.features import FEATURE_COLUMNS, build_decision_features
from ml.real_features import engineer_real_features, events_to_real_rows
from ml.train import DEFAULT_ARTIFACT_DIR


def _incident(data_dir: str | Path, scenario_id: str) -> dict[str, str]:
    with (Path(data_dir) / "incidents.csv").open("r", encoding="utf-8", newline="") as stream:
        for record in csv.DictReader(stream):
            if record["scenario_id"] == scenario_id:
                return record
    raise KeyError(f"No incident exists for scenario {scenario_id!r}.")


def _real_wallet_scores(replay: Any, artifact: dict[str, Any]) -> dict[str, tuple[float, int]]:
    events = list(replay.transactions)
    rows = events_to_real_rows(events)
    if rows.empty:
        return {}
    probabilities = artifact["pipeline"].predict_proba(engineer_real_features(rows))
    classes = list(artifact["pipeline"].classes_)
    p = probabilities[:, classes.index(1)]
    grouped: dict[str, list[float]] = {}
    for event, probability in zip(events, p):
        score = float(np.clip(probability, 0.0, 1.0))
        for wallet_id in (str(event.sender_wallet), str(event.receiver_wallet)):
            grouped.setdefault(wallet_id, []).append(score)
    # Recent/high-risk behavior matters more than an undifferentiated mean while
    # avoiding the instability of using max(probability) as the whole wallet score.
    return {wallet: (float(np.clip(0.6 * max(values) + 0.4 * sum(values) / len(values), 0, 1)), len(values)) for wallet, values in grouped.items()}


def predict_scenario(scenario_id: str, *, data_dir: str | Path = DEFAULT_DATA_DIR, artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR) -> dict[str, Any]:
    import joblib
    from core.simulator import TransactionSimulator

    artifacts = Path(artifact_dir)
    incident = _incident(data_dir, scenario_id)
    replay = TransactionSimulator(Path(data_dir) / "flowfreeze.db").replay(scenario_id)
    real_path = artifacts / "real_fraud_model.joblib"
    synthetic_fraud_path = artifacts / "fraud_model.joblib"
    next_path = artifacts / "next_move_model.joblib"
    real = joblib.load(real_path) if real_path.exists() else None
    synthetic_fraud = joblib.load(synthetic_fraud_path) if synthetic_fraud_path.exists() else None
    next_move = joblib.load(next_path) if next_path.exists() else None
    if real is None and synthetic_fraud is None:
        return {
            "scenario_id": scenario_id, "as_of": incident["analysis_at"], "synthetic": True,
            "model_status": "unavailable", "fraud_model": None, "fraud_threshold": None,
            "fraud_model_source": "unavailable", "scenario_data_source": "synthetic_flowfreeze_scenario",
            "wallet_predictions": {}, "warning": "Real public-data model artifacts are not installed; no fraud score was fabricated. Train with python -m ml.train_real.",
        }

    wallet_predictions: dict[str, dict[str, Any]] = {}
    if real is not None:
        scores = _real_wallet_scores(replay, real)
        threshold = float(real["decision_threshold"])
        fraud_model = real["model_name"]
        fraud_source = "real_transaction_dataset"
        for wallet_id, (risk, _) in scores.items():
            wallet_predictions[wallet_id] = {"fraud_risk": risk, "fraud_flag_at_threshold": bool(risk >= threshold), "next_move_probabilities": None}
    else:
        table = build_decision_features(data_dir)
        rows = table[table["scenario_id"] == scenario_id].copy()
        features = rows[FEATURE_COLUMNS]
        classes = list(synthetic_fraud["pipeline"].classes_)
        probabilities = synthetic_fraud["pipeline"].predict_proba(features)[:, classes.index(1)]
        threshold = float(synthetic_fraud["decision_threshold"])
        fraud_model, fraud_source = synthetic_fraud["model_name"], "synthetic_flowfreeze_data"
        for index, row in enumerate(rows.to_dict("records")):
            wallet_predictions[str(row["wallet_id"])] = {"fraud_risk": float(probabilities[index]), "fraud_flag_at_threshold": bool(probabilities[index] >= threshold), "next_move_probabilities": None}

    if next_move is not None:
        table = build_decision_features(data_dir)
        rows = table[table["scenario_id"] == scenario_id].copy()
        movement_classes = list(next_move["pipeline"].classes_)
        movement_probabilities = apply_multiclass_calibrators(next_move["pipeline"].predict_proba(rows[FEATURE_COLUMNS]), movement_classes, next_move["calibrators"])
        for index, row in enumerate(rows.to_dict("records")):
            wallet_predictions.setdefault(str(row["wallet_id"]), {"fraud_risk": None, "fraud_flag_at_threshold": None, "next_move_probabilities": None})["next_move_probabilities"] = {label: float(movement_probabilities[index, class_index]) for class_index, label in enumerate(movement_classes)}

    return {
        "scenario_id": scenario_id, "as_of": incident["analysis_at"], "synthetic": True,
        "model_status": "available", "fraud_model": fraud_model, "fraud_threshold": threshold,
        "fraud_model_source": fraud_source, "scenario_data_source": "synthetic_flowfreeze_scenario",
        "next_move_model_source": "synthetic_flowfreeze_data" if next_move is not None else "unavailable",
        "wallet_predictions": wallet_predictions,
        "wallet_risk_aggregation": "0.6 * max(transaction_probability) + 0.4 * mean(transaction_probability), per wallet",
        "warning": "FlowFreeze scenario data is synthetic. Public transaction model scores are decision-support signals, not upay BD production/customer probabilities." if real is not None else "Synthetic FlowFreeze model scores are not upay BD production risk estimates.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict fraud risk for a synthetic FlowFreeze scenario.")
    parser.add_argument("scenario_id")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    args = parser.parse_args()
    print(json.dumps(predict_scenario(args.scenario_id, data_dir=args.data_dir, artifact_dir=args.artifact_dir), indent=2))

if __name__ == "__main__":
    main()
