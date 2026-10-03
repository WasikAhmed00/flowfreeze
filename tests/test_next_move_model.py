from __future__ import annotations

import joblib

from ml.features import FEATURE_COLUMNS, build_feature_table


def test_next_move_prediction_uses_trained_model(trained_fixture):
    table = build_feature_table(trained_fixture["data_dir"])
    artifact = joblib.load(trained_fixture["artifact_dir"] / "next_move_model.joblib")
    model = artifact["pipeline"]
    predictions = model.predict(table[FEATURE_COLUMNS])
    probabilities = model.predict_proba(table[FEATURE_COLUMNS])

    assert len(predictions) == len(table)
    assert set(predictions).issubset({"forward", "cashout", "no_movement"})
    assert set(artifact["classes"]).issubset({"forward", "cashout", "no_movement"})
    assert probabilities.shape[0] == len(table)
    assert ((probabilities >= 0) & (probabilities <= 1)).all()
