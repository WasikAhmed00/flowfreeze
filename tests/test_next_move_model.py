from __future__ import annotations

import joblib

from ml.calibration import apply_multiclass_calibrators
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


def test_next_move_calibration_preserves_cashout_signal(trained_fixture):
    table = build_feature_table(trained_fixture["data_dir"])
    test = table[table["split"] == "test"]
    artifact = joblib.load(trained_fixture["artifact_dir"] / "next_move_model.joblib")
    classes = list(artifact["pipeline"].classes_)
    probabilities = apply_multiclass_calibrators(
        artifact["pipeline"].predict_proba(test[FEATURE_COLUMNS]),
        classes,
        artifact["calibrators"],
    )
    predictions = [classes[index] for index in probabilities.argmax(axis=1)]
    cashout_rows = test["expected_next_action"] == "cashout"

    assert artifact["raw_probability_blend"] == 0.5
    assert cashout_rows.any()
    assert any(actual == predicted == "cashout" for actual, predicted in zip(test["expected_next_action"], predictions))
