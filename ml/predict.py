"""Load saved models and predict wallet risk and next movement for a scenario."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from data_generator.config import DEFAULT_DATA_DIR
from ml.features import FEATURE_COLUMNS, build_decision_features
from ml.train import DEFAULT_ARTIFACT_DIR
from ml.calibration import apply_multiclass_calibrators


def predict_scenario(
    scenario_id: str,
    *,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
) -> dict[str, Any]:
    import joblib

    artifacts = Path(artifact_dir)
    fraud = joblib.load(artifacts / "fraud_model.joblib")
    next_move = joblib.load(artifacts / "next_move_model.joblib")
    table = build_decision_features(data_dir)
    rows = table[table["scenario_id"] == scenario_id].copy()
    if rows.empty:
        raise KeyError(f"No prediction rows exist for scenario {scenario_id!r}.")
    features = rows[FEATURE_COLUMNS]
    fraud_classes = list(fraud["pipeline"].classes_)
    fraud_probabilities = fraud["pipeline"].predict_proba(features)[:, fraud_classes.index(1)]
    movement_classes = list(next_move["pipeline"].classes_)
    movement_probabilities = apply_multiclass_calibrators(
        next_move["pipeline"].predict_proba(features), movement_classes, next_move["calibrators"],
    )
    predictions = {}
    for index, row in enumerate(rows.to_dict("records")):
        predictions[str(row["wallet_id"])] = {
            "fraud_risk": float(fraud_probabilities[index]),
            "fraud_flag_at_threshold": bool(fraud_probabilities[index] >= fraud["decision_threshold"]),
            "next_move_probabilities": {
                label: float(movement_probabilities[index, class_index])
                for class_index, label in enumerate(movement_classes)
            },
        }
    incident_path = Path(data_dir) / "incidents.csv"
    incident_row = None
    import csv
    with incident_path.open("r", encoding="utf-8", newline="") as stream:
        for record in csv.DictReader(stream):
            if record["scenario_id"] == scenario_id:
                incident_row = record
                break
    if incident_row is None:
        raise KeyError(f"No incident exists for scenario {scenario_id!r}.")
    return {
        "scenario_id": scenario_id,
        "as_of": incident_row["analysis_at"],
        "synthetic": True,
        "model_status": "available",
        "fraud_model": fraud["model_name"],
        "fraud_threshold": float(fraud["decision_threshold"]),
        "next_move_window_minutes": int(next_move["prediction_window_minutes"]),
        "wallet_predictions": predictions,
        "warning": "Synthetic model scores are not upay BD production risk estimates.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict fraud risk and next movement for a synthetic FlowFreeze scenario.")
    parser.add_argument("scenario_id", help="Scenario ID such as SCN-06-FANOUT-CASHOUT-0001")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    args = parser.parse_args()
    print(json.dumps(predict_scenario(args.scenario_id, data_dir=args.data_dir, artifact_dir=args.artifact_dir), indent=2))


if __name__ == "__main__":
    main()
