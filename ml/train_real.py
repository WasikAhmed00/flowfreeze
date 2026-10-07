"""Train the FlowFreeze fraud classifier on a bounded public transaction sample."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, confusion_matrix, f1_score, precision_score,
    recall_score, roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.real_features import REAL_FEATURE_COLUMNS, engineer_real_features, load_real_transactions

DEFAULT_ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "ml" / "Fraud.csv"
NUMERIC = [c for c in REAL_FEATURE_COLUMNS if c != "type"]
CATEGORICAL = ["type"]


def _preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), NUMERIC),
        ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), CATEGORICAL),
    ])


def _candidates(seed: int) -> dict[str, Pipeline]:
    return {
        "logistic_regression": Pipeline([("preprocess", _preprocessor()), ("classifier", LogisticRegression(max_iter=1500, class_weight="balanced", random_state=seed))]),
        "random_forest": Pipeline([("preprocess", _preprocessor()), ("classifier", RandomForestClassifier(n_estimators=180, min_samples_leaf=2, class_weight="balanced_subsample", random_state=seed, n_jobs=-1))]),
    }


def _split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    """Prefer chronological 60/20/20 bins; fall back only for tiny fixtures."""
    ordered = frame.sort_values(["step"]).reset_index(drop=True)
    steps = ordered["step"].to_numpy()
    if len(ordered) >= 30 and ordered["isFraud"].sum() >= 3 and len(np.unique(steps)) >= 3:
        q60, q80 = np.quantile(steps, [0.60, 0.80])
        train, validation, test = ordered[steps <= q60], ordered[(steps > q60) & (steps <= q80)], ordered[steps > q80]
        if all(len(part) > 0 and part["isFraud"].nunique() == 2 for part in (train, validation, test)):
            return train, validation, test, "chronological_by_step_60_20_20"
    # A small-file fallback keeps the CLI usable for unit tests; production-sized MVP data uses time split.
    from sklearn.model_selection import train_test_split
    train, remainder = train_test_split(frame, test_size=0.4, random_state=42, stratify=frame["isFraud"])
    validation, test = train_test_split(remainder, test_size=0.5, random_state=42, stratify=remainder["isFraud"])
    return train, validation, test, "stratified_random_fallback_for_small_or_single-class_time_bins"


def _probabilities(model: Pipeline, x: pd.DataFrame) -> np.ndarray:
    classes = list(model.classes_)
    return model.predict_proba(x)[:, classes.index(1)]


def _threshold(y: pd.Series, p: np.ndarray) -> float:
    candidates = np.unique(np.r_[0.05, np.linspace(0.05, 0.95, 91), p])
    scores = [(f1_score(y, p >= t, zero_division=0), -t, float(t)) for t in candidates]
    return max(scores)[2]


def _metrics(y: pd.Series, p: np.ndarray, threshold: float) -> dict[str, Any]:
    pred = (p >= threshold).astype(int)
    return {
        "threshold": float(threshold), "roc_auc": float(roc_auc_score(y, p)) if y.nunique() > 1 else None,
        "pr_auc_average_precision": float(average_precision_score(y, p)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "confusion_matrix_labels_0_1": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
        "fraud_class_support": int((np.asarray(y) == 1).sum()),
    }


def train_real(data_path: str | Path = DEFAULT_DATA_PATH, artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR, *, max_rows: int = 10_000, seed: int = 42) -> dict[str, Any]:
    frame = load_real_transactions(data_path, max_rows=max_rows)
    if frame["isFraud"].nunique() < 2 or frame["isFraud"].sum() < 3:
        raise ValueError("The bounded sample must contain at least three fraudulent and non-fraudulent rows.")
    train, validation, test, split_strategy = _split(frame)
    x_train, y_train = engineer_real_features(train), train["isFraud"]
    x_validation, y_validation = engineer_real_features(validation), validation["isFraud"]
    candidates: dict[str, Any] = {}
    for name, model in _candidates(seed).items():
        model.fit(x_train, y_train)
        p = _probabilities(model, x_validation)
        candidates[name] = {"model": model, "pr_auc": float(average_precision_score(y_validation, p)), "roc_auc": float(roc_auc_score(y_validation, p))}
    selected_name = max(candidates, key=lambda n: (candidates[n]["pr_auc"], candidates[n]["roc_auc"], n == "logistic_regression"))
    threshold = _threshold(y_validation, _probabilities(candidates[selected_name]["model"], x_validation))
    final_model = _candidates(seed)[selected_name]
    final_model.fit(engineer_real_features(pd.concat([train, validation])), pd.concat([y_train, y_validation]))
    p_test = _probabilities(final_model, engineer_real_features(test))
    metrics = _metrics(test["isFraud"], p_test, threshold)
    out = Path(artifact_dir); out.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": final_model, "feature_columns": REAL_FEATURE_COLUMNS, "model_name": selected_name, "decision_threshold": threshold, "positive_class": 1}, out / "real_fraud_model.joblib")
    joblib.dump(final_model.named_steps["preprocess"], out / "real_preprocessor.joblib")
    metadata = {
        "source": "real_transaction_dataset", "dataset": Path(data_path).name, "dataset_path": str(Path(data_path)), "synthetic": False,
        "sample_rows_requested": max_rows, "rows_loaded": len(frame), "feature_columns": REAL_FEATURE_COLUMNS,
        "excluded_from_features": ["isFraud", "nameOrig", "nameDest", "isFlaggedFraud"],
        "preprocessing_version": "real-v1-onehot-median-scaled", "model_type": selected_name, "training_seed": seed,
        "split_strategy": split_strategy, "split_sizes": {"train": len(train), "validation": len(validation), "test": len(test)},
        "class_distribution": {str(k): int(v) for k, v in frame["isFraud"].value_counts().sort_index().items()},
        "validation_model_comparison": {k: {x: v for x, v in val.items() if x != "model"} for k, val in candidates.items()},
        "evaluation_metrics": metrics, "threshold": float(threshold), "trained_at": datetime.now(timezone.utc).isoformat(), "scikit_learn_version": sklearn.__version__,
        "warning": "Fraud.csv is a public simulated transaction dataset, not upay BD production/customer data; FlowFreeze scenarios remain synthetic.",
    }
    (out / "real_model_metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the bounded public transaction fraud model.")
    parser.add_argument("--data-path", type=Path, default=Path(__import__("os").environ.get("FLOWFREEZE_REAL_DATA_PATH", DEFAULT_DATA_PATH)))
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--max-rows", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(train_real(args.data_path, args.artifact_dir, max_rows=args.max_rows, seed=args.seed), indent=2))

if __name__ == "__main__":
    main()
