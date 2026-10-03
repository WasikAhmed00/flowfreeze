from __future__ import annotations

import joblib
import pytest
from sklearn.exceptions import NotFittedError

from ml.features import FEATURE_COLUMNS, build_feature_table
from ml.train import _fraud_candidates


def test_fraud_model_requires_training(generated_fixture):
    table = build_feature_table(generated_fixture["data_dir"])
    model = _fraud_candidates(seed=42)["logistic_regression"]

    with pytest.raises(NotFittedError):
        model.predict_proba(table[FEATURE_COLUMNS].head(1))


def test_trained_fraud_model_predicts_probabilities(trained_fixture):
    table = build_feature_table(trained_fixture["data_dir"])
    artifact = joblib.load(trained_fixture["artifact_dir"] / "fraud_model.joblib")
    model = artifact["pipeline"]
    probabilities = model.predict_proba(table[FEATURE_COLUMNS])
    predictions = model.predict(table[FEATURE_COLUMNS])

    assert probabilities.shape == (len(table), 2)
    assert ((probabilities >= 0) & (probabilities <= 1)).all()
    assert len(predictions) == len(table)
    assert set(predictions).issubset({0, 1})
    assert artifact["model_name"] in {"logistic_regression", "random_forest"}
