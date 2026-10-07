from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ml.real_features import REAL_FEATURE_COLUMNS, engineer_real_features, events_to_real_rows, load_real_transactions
from ml.train_real import train_real


def _dataset(path: Path) -> None:
    rows = []
    for step in range(1, 61):
        for i in range(4):
            fraud = int(i == 3 and step % 5 == 0)
            rows.append({"step": step, "type": "TRANSFER" if fraud else "PAYMENT", "amount": 900 + step * 2, "oldbalanceOrg": 1000 + step * 3, "newbalanceOrig": 100 + step, "oldbalanceDest": 0, "newbalanceDest": 900 + step * 2, "isFraud": fraud, "isFlaggedFraud": 0})
    pd.DataFrame(rows).to_csv(path, index=False)


def test_loading_and_feature_order(tmp_path):
    path = tmp_path / "Fraud.csv"; _dataset(path)
    frame = load_real_transactions(path, max_rows=100)
    assert list(engineer_real_features(frame).columns) == REAL_FEATURE_COLUMNS
    assert "isFraud" not in engineer_real_features(frame).columns


def test_real_model_artifacts_and_deterministic_inference(tmp_path):
    data = tmp_path / "Fraud.csv"; _dataset(data)
    artifacts = tmp_path / "artifacts"
    metadata = train_real(data, artifacts, max_rows=240, seed=7)
    assert (artifacts / "real_fraud_model.joblib").exists()
    assert (artifacts / "real_preprocessor.joblib").exists()
    assert (artifacts / "real_model_metadata.json").exists()
    assert 0 <= metadata["threshold"] <= 1
    assert metadata["evaluation_metrics"]["pr_auc_average_precision"] >= 0


def test_missing_values_are_dropped(tmp_path):
    path = tmp_path / "Fraud.csv"; _dataset(path)
    frame = pd.read_csv(path); frame.loc[0, "amount"] = None; frame.to_csv(path, index=False)
    assert len(load_real_transactions(path)) == 239
