"""Held-out evaluation metrics for FlowFreeze's synthetic wallet models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
)
from sklearn.preprocessing import label_binarize

from data_generator.config import DEFAULT_DATA_DIR
from ml.features import FEATURE_COLUMNS, build_feature_table

DEFAULT_ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
NEXT_MOVE_CLASSES = ["cashout", "forward", "no_movement"]


def binary_metrics(y_true: Any, probabilities: Any, threshold: float = 0.5) -> dict[str, Any]:
    y_true = np.asarray(y_true, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    predicted = (probabilities >= threshold).astype(int)
    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y_true, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, predicted)),
        "precision": float(precision_score(y_true, predicted, zero_division=0)),
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "f1": float(f1_score(y_true, predicted, zero_division=0)),
        "pr_auc_average_precision": float(average_precision_score(y_true, probabilities)),
        "confusion_matrix_labels_0_1": confusion_matrix(y_true, predicted, labels=[0, 1]).tolist(),
        "class_report": classification_report(y_true, predicted, labels=[0, 1], output_dict=True, zero_division=0),
    }


def multiclass_metrics(y_true: Any, probabilities: Any, classes: list[str] | None = None) -> dict[str, Any]:
    y_true = np.asarray(y_true, dtype=str)
    probabilities = np.asarray(probabilities, dtype=float)
    classes = classes or NEXT_MOVE_CLASSES
    predicted = np.asarray(classes, dtype=object)[probabilities.argmax(axis=1)]
    binarized = label_binarize(y_true, classes=classes)
    return {
        "classes": list(classes),
        "accuracy": float(accuracy_score(y_true, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, predicted)),
        "precision_macro": float(precision_score(y_true, predicted, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_true, predicted, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_true, predicted, average="macro", zero_division=0)),
        "f1_weighted": float(f1_score(y_true, predicted, average="weighted", zero_division=0)),
        "pr_auc_macro_ovr": float(average_precision_score(binarized, probabilities, average="macro")),
        "log_loss": float(log_loss(y_true, probabilities, labels=classes)),
        "brier_score_multiclass": float(np.mean(np.sum((probabilities - binarized) ** 2, axis=1))),
        "confusion_matrix_labels_classes_order": confusion_matrix(y_true, predicted, labels=classes).tolist(),
        "class_report": classification_report(y_true, predicted, labels=classes, output_dict=True, zero_division=0),
    }


def evaluate_saved_models(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
) -> dict[str, Any]:
    import joblib

    table = build_feature_table(data_dir)
    test = table[table["split"] == "test"]
    if test.empty:
        raise ValueError("No held-out test rows are present in the generated dataset.")
    x_test = test[FEATURE_COLUMNS]
    fraud = joblib.load(Path(artifact_dir) / "fraud_model.joblib")
    movement = joblib.load(Path(artifact_dir) / "next_move_model.joblib")
    fraud_p1 = fraud["pipeline"].predict_proba(x_test)[:, list(fraud["pipeline"].classes_).index(1)]
    next_raw = movement["pipeline"].predict_proba(x_test)
    from ml.calibration import apply_multiclass_calibrators
    next_classes = list(movement["pipeline"].classes_)
    next_prob = apply_multiclass_calibrators(next_raw, next_classes, movement["calibrators"])
    results = {
        "test_wallet_rows": int(len(test)),
        "test_scenario_cases": int(test["scenario_id"].nunique()),
        "fraud": binary_metrics(test["fraud_flag"], fraud_p1, fraud["decision_threshold"]),
        "next_move": multiclass_metrics(test["expected_next_action"], next_prob, next_classes),
    }
    path = Path(artifact_dir) / "metrics.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    existing["held_out_test"] = results
    path.write_text(json.dumps(existing, indent=2, allow_nan=False), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate trained FlowFreeze models on held-out synthetic test cases.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    args = parser.parse_args()
    print(json.dumps(evaluate_saved_models(args.data_dir, args.artifact_dir), indent=2))


if __name__ == "__main__":
    main()
