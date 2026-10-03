"""Train leakage-aware fraud and next-move models on case-level splits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.metrics import f1_score, average_precision_score

from data_generator.config import DEFAULT_DATA_DIR, DEFAULT_RANDOM_SEED
from ml.calibration import apply_multiclass_calibrators, fit_multiclass_calibrators
from ml.evaluate import binary_metrics, multiclass_metrics
from ml.features import CATEGORICAL_FEATURES, FEATURE_COLUMNS, NUMERIC_FEATURES, build_feature_table

DEFAULT_ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"


def _preprocessor() -> ColumnTransformer:
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
    ])
    return ColumnTransformer([
        ("numeric", numeric, NUMERIC_FEATURES),
        ("categorical", categorical, CATEGORICAL_FEATURES),
    ])


def _fraud_candidates(seed: int) -> dict[str, Pipeline]:
    return {
        "logistic_regression": Pipeline([
            ("preprocess", _preprocessor()),
            ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed, solver="lbfgs")),
        ]),
        "random_forest": Pipeline([
            ("preprocess", _preprocessor()),
            ("classifier", RandomForestClassifier(
                n_estimators=300, min_samples_leaf=3, max_features="sqrt",
                class_weight="balanced_subsample", random_state=seed, n_jobs=-1,
            )),
        ]),
    }


def _select_f1_threshold(y_true: Any, probabilities: Any) -> float:
    candidates = np.unique(np.concatenate(([0.5], np.asarray(probabilities, dtype=float))))
    scored = [(float(f1_score(y_true, probabilities >= threshold, zero_division=0)), float(threshold)) for threshold in candidates]
    return max(scored, key=lambda item: (item[0], item[1]))[1]


def _positive_probability(model: Pipeline, x: pd.DataFrame) -> np.ndarray:
    classes = list(model.classes_)
    return model.predict_proba(x)[:, classes.index(1)]


def _split_guard(table: pd.DataFrame) -> None:
    expected = {"train", "validation", "test"}
    found = set(table["split"].unique())
    if not expected.issubset(found):
        raise ValueError(f"Expected train, validation, and test splits; found {sorted(found)}.")
    seen: dict[str, set[str]] = {}
    for split in expected:
        seen[split] = set(table.loc[table["split"] == split, "scenario_id"])
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        overlap = seen[left] & seen[right]
        if overlap:
            raise ValueError(f"Scenario leakage between {left} and {right}: {sorted(overlap)[:3]}.")


def train_models(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    seed: int = DEFAULT_RANDOM_SEED,
) -> dict[str, Any]:
    import joblib

    table = build_feature_table(data_dir)
    _split_guard(table)
    train = table[table["split"] == "train"]
    validation = table[table["split"] == "validation"]
    test = table[table["split"] == "test"]
    x_train, x_validation = train[FEATURE_COLUMNS], validation[FEATURE_COLUMNS]
    y_train, y_validation = train["fraud_flag"].astype(int), validation["fraud_flag"].astype(int)

    candidates: dict[str, dict[str, Any]] = {}
    for name, model in _fraud_candidates(seed).items():
        model.fit(x_train, y_train)
        probabilities = _positive_probability(model, x_validation)
        candidates[name] = {
            "model": model,
            "validation_pr_auc_average_precision": float(average_precision_score(y_validation, probabilities)),
            "validation_f1_at_0_5": float(f1_score(y_validation, probabilities >= 0.5, zero_division=0)),
        }
    # Select model class by validation PR-AUC. Stable tie-break prefers the transparent logistic baseline.
    selected_name = max(
        ("logistic_regression", "random_forest"),
        key=lambda name: (candidates[name]["validation_pr_auc_average_precision"], name == "logistic_regression"),
    )
    selected_validation_model = candidates[selected_name]["model"]
    selected_validation_probabilities = _positive_probability(selected_validation_model, x_validation)
    threshold = _select_f1_threshold(y_validation, selected_validation_probabilities)

    fraud_final = _fraud_candidates(seed)[selected_name]
    fraud_final.fit(x_train, y_train)
    next_move = Pipeline([
        ("preprocess", _preprocessor()),
        ("classifier", LogisticRegression(
            max_iter=2500, class_weight="balanced", random_state=seed, solver="lbfgs",
        )),
    ])
    next_move.fit(x_train, train["expected_next_action"].astype(str))
    next_classes = list(next_move.classes_)
    next_validation_raw = next_move.predict_proba(x_validation)
    next_calibrators = fit_multiclass_calibrators(
        next_validation_raw, validation["expected_next_action"], next_classes, seed=seed,
    )
    next_validation_calibrated = apply_multiclass_calibrators(next_validation_raw, next_classes, next_calibrators)

    x_test, y_test = test[FEATURE_COLUMNS], test["fraud_flag"].astype(int)
    fraud_test_probabilities = _positive_probability(fraud_final, x_test)
    next_test_raw = next_move.predict_proba(x_test)
    next_test_probabilities = apply_multiclass_calibrators(next_test_raw, next_classes, next_calibrators)
    validation_metrics = {
        "fraud_model_comparison": {
            name: {key: value for key, value in record.items() if key != "model"}
            for name, record in candidates.items()
        },
        "selected_fraud_model": selected_name,
        "fraud_threshold_selected_on_validation_for_f1": threshold,
        "fraud_validation": binary_metrics(y_validation, selected_validation_probabilities, threshold),
    }
    validation_metrics["next_move_calibration"] = {
        "method": "one_vs_rest_platt_scaled_then_renormalized_with_50pct_raw_blend",
        "fit_rows": int(len(validation)),
        "validation_scores_are_calibration_fit_data": True,
        "calibrated_validation_diagnostics_not_held_out": multiclass_metrics(
            validation["expected_next_action"], next_validation_calibrated, next_classes,
        ),
    }
    test_metrics = {
        "wallet_rows": int(len(test)),
        "scenario_cases": int(test["scenario_id"].nunique()),
        "fraud": binary_metrics(y_test, fraud_test_probabilities, threshold),
        "next_move": multiclass_metrics(test["expected_next_action"], next_test_probabilities, next_classes),
    }

    out_dir = Path(artifact_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "pipeline": fraud_final,
        "feature_columns": FEATURE_COLUMNS,
        "model_name": selected_name,
        "decision_threshold": threshold,
        "positive_class": 1,
    }, out_dir / "fraud_model.joblib")
    joblib.dump({
        "pipeline": next_move,
        "feature_columns": FEATURE_COLUMNS,
        "classes": next_classes,
        "calibrators": next_calibrators,
        "calibration_method": "one_vs_rest_platt_scaled_then_renormalized_with_50pct_raw_blend",
        "raw_probability_blend": 0.5,
        "prediction_window_minutes": 5,
    }, out_dir / "next_move_model.joblib")
    metrics = {
        "synthetic_only": True,
        "warning": "Synthetic generated labels and distributions are not evidence of upay BD production performance.",
        "seed": int(seed),
        "scikit_learn_version": sklearn.__version__,
        "feature_count": len(FEATURE_COLUMNS),
        "feature_columns": FEATURE_COLUMNS,
        "excluded_from_features": ["scenario_id", "wallet_id", "split", "fraud_flag", "tainted_amount", "hop_number", "cashout_flag", "expected_next_action", "fraud_source_wallet", "all transactions after analysis_at"],
        "split_unit": "scenario_id; no scenario appears in multiple splits",
        "split_scenarios": {split: int(table.loc[table["split"] == split, "scenario_id"].nunique()) for split in ("train", "validation", "test")},
        "split_wallet_rows": {split: int((table["split"] == split).sum()) for split in ("train", "validation", "test")},
        "label_distribution": {
            "fraud_flag": {str(key): int(value) for key, value in table["fraud_flag"].value_counts().items()},
            "expected_next_action": {str(key): int(value) for key, value in table["expected_next_action"].value_counts().items()},
        },
        "fraud_model_selection": validation_metrics,
        "held_out_test": test_metrics,
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train FlowFreeze synthetic fraud and next-move models.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED)
    args = parser.parse_args()
    metrics = train_models(args.data_dir, args.artifact_dir, args.seed)
    print(json.dumps({
        "artifacts": str(args.artifact_dir.resolve()),
        "selected_fraud_model": metrics["fraud_model_selection"]["selected_fraud_model"],
        "fraud_test": metrics["held_out_test"]["fraud"],
        "next_move_test": metrics["held_out_test"]["next_move"],
        "warning": metrics["warning"],
    }, indent=2))


if __name__ == "__main__":
    main()
