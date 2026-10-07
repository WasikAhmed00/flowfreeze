from __future__ import annotations

import json
import argparse
import shutil
import sqlite3
from datetime import datetime, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routes import metrics as metrics_route
from core.fairness_analysis import (
    SEGMENT_COLUMNS,
    _binary_metrics,
    _false_positive_impact,
    _parse_thresholds,
    _with_segments,
    run_fairness_evaluation,
)
from ml.features import build_feature_table


def test_binary_metrics_and_small_support_flags():
    metrics = _binary_metrics([0, 0, 1, 1], [0.9, 0.4, 0.8, 0.2], 0.5, min_group_size=4, min_class_support=2)
    assert (metrics["true_positives"], metrics["false_positives"], metrics["true_negatives"], metrics["false_negatives"]) == (1, 1, 1, 1)
    assert metrics["precision"] == metrics["false_positive_rate"] == metrics["false_negative_rate"] == 0.5
    assert metrics["true_positive_rate"] == 0.5
    assert metrics["reliability"]["metric_reliable"]["pr_auc_average_precision"] is True

    sparse = _binary_metrics([0, 0, 0], [0.1, 0.8, 0.2], 0.5, min_group_size=3, min_class_support=2)
    assert sparse["reliability"]["status"] == "unreliable_small_or_one_class_sample"
    assert sparse["pr_auc_average_precision"] is None
    assert sparse["reliability"]["metric_reliable"]["true_positive_rate"] is False


def test_cohort_cutpoints_are_train_only_and_use_existing_synthetic_profiles(generated_fixture, tmp_path):
    source = generated_fixture["data_dir"]
    table = build_feature_table(source)
    _, original_boundaries = _with_segments(table, source)
    altered = tmp_path / "altered-data"
    shutil.copytree(source, altered)
    profiles = pd.read_csv(altered / "wallets.csv")
    test_ids = set(table.loc[table["split"] == "test", "scenario_id"])
    is_test = profiles["scenario_id"].isin(test_ids)
    profiles.loc[is_test, "transaction_frequency"] = 999999
    profiles.loc[is_test, "average_transaction_amount"] = 999999999
    profiles.to_csv(altered / "wallets.csv", index=False)
    cohorts, changed_boundaries = _with_segments(table, altered)
    assert original_boundaries["transaction_activity_bucket"]["train_cutpoints"] == changed_boundaries["transaction_activity_bucket"]["train_cutpoints"]
    assert original_boundaries["amount_profile_bucket"]["train_cutpoints_bdt"] == changed_boundaries["amount_profile_bucket"]["train_cutpoints_bdt"]
    assert set(SEGMENT_COLUMNS).issubset(cohorts.columns)
    assert not {"race", "religion", "political_affiliation"}.intersection(cohorts.columns)


def test_false_positive_legitimate_value_is_deduplicated():
    population = pd.DataFrame([
        {"scenario_id": "s-1", "wallet_id": "w-a", "fraud_flag": 0, **{column: "cohort" for column in SEGMENT_COLUMNS}},
        {"scenario_id": "s-1", "wallet_id": "w-b", "fraud_flag": 0, **{column: "cohort" for column in SEGMENT_COLUMNS}},
    ])
    now = pd.Timestamp(datetime(2026, 9, 1, tzinfo=timezone.utc))
    transactions = {"s-1": [{
        "_time": now, "transaction_id": "tx-1", "sender_wallet": "w-a", "receiver_wallet": "w-b", "amount": "1250.00",
    }]}
    cutoffs = {"s-1": datetime(2026, 9, 2, tzinfo=timezone.utc)}
    truth = {("s-1", "w-a"): 0, ("s-1", "w-b"): 0}
    wallet_types = {("s-1", "w-a"): "individual", ("s-1", "w-b"): "individual"}
    impact = _false_positive_impact(population, [True, True], transactions, cutoffs, truth, wallet_types)
    assert impact["false_positive_count"] == 2
    assert impact["false_positive_rate"] == 1.0
    assert impact["affected_legitimate_transaction_count"] == 1
    assert impact["legitimate_value_affected_bdt"] == 1250.0
    assert impact["average_legitimate_value_affected_bdt"] == 1250.0
    assert impact["median_legitimate_value_affected_bdt"] == 1250.0
    assert impact["cases_per_segment"]["customer_type"]["cohort"] == 1


def _has_identifiers(value):
    if isinstance(value, dict):
        return any(key in {"wallet_id", "scenario_id", "transaction_id", "case_id", "customer_id"} or _has_identifiers(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_has_identifiers(item) for item in value)
    return False


def test_end_to_end_fairness_artifacts_use_heldout_test_and_validation_sweep(trained_fixture, tmp_path):
    result = run_fairness_evaluation(
        trained_fixture["data_dir"], trained_fixture["artifact_dir"], tmp_path,
        min_group_size=5, min_class_support=2,
    )
    report = result["fairness_evaluation"]
    harm = result["false_positive_impact"]
    assert report["synthetic"] is True
    assert report["evaluation_split"] == "test"
    assert report["test_threshold_source"].startswith("Existing model threshold selected on validation")
    assert report["threshold_analysis"]["split"] == "validation"
    assert report["threshold_analysis"]["validation_metrics_are_selection_data"] is True
    points = report["threshold_analysis"]["points"]
    assert set((0.5, 0.6, 0.7, 0.8, 0.9)).issubset({point["threshold"] for point in points})
    assert any(point["matches_model_selected_threshold"] for point in points)
    assert set(report["test_metrics_by_segment"]) == set(SEGMENT_COLUMNS)
    assert len(report["intervention_policy_comparison"]["results"]) == 2
    assert all(item["automatic_execution"] is False for item in report["intervention_policy_comparison"]["results"])
    assert all("missed_fraud_rate" in item and "precision" in item and "analyst_workload" in item for item in report["intervention_policy_comparison"]["results"])
    assert all("explanation_strength_distribution" in item for item in report["intervention_policy_comparison"]["results"])
    evidence = report["intervention_policy_comparison"]["evidence_rule"]
    assert evidence["human_review_required"] is True and evidence["automatic_execution"] is False
    assert harm["overall"]["false_positive_count"] >= 0
    assert not _has_identifiers(report)
    assert not _has_identifiers(harm)
    assert {"fairness_evaluation.json", "fairness_evaluation.csv", "false_positive_impact.json", "false_positive_impact.csv"}.issubset({p.name for p in tmp_path.iterdir()})
    csv_contents = (tmp_path / "fairness_evaluation.csv").read_text(encoding="utf-8").lower()
    assert "scenario_id" not in csv_contents and "wallet_id" not in csv_contents
    impact_csv = (tmp_path / "false_positive_impact.csv").read_text(encoding="utf-8").lower()
    assert "scenario_id" not in impact_csv and "wallet_id" not in impact_csv


def test_thresholds_are_configurable_and_validated(trained_fixture, tmp_path):
    assert _parse_thresholds("0.9,0.5,0.9") == (0.5, 0.9)
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_thresholds("-0.1,1.1")
    result = run_fairness_evaluation(
        trained_fixture["data_dir"], trained_fixture["artifact_dir"], tmp_path / "custom-thresholds",
        thresholds=(0.4, 0.9),
    )
    points = result["fairness_evaluation"]["threshold_analysis"]["points"]
    assert {0.4, 0.9}.issubset({point["threshold"] for point in points})
    assert any(point["matches_model_selected_threshold"] for point in points)


def _api_client(tmp_path, monkeypatch):
    database = tmp_path / "fairness-api.db"
    with sqlite3.connect(database) as connection:
        connection.executescript("CREATE TABLE incidents (incident_id TEXT); CREATE TABLE transactions (transaction_id TEXT); CREATE TABLE wallets (wallet_id TEXT);")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    return TestClient(app)


def test_fairness_api_rbac_and_aggregate_only_artifacts(tmp_path, monkeypatch):
    fairness_path = tmp_path / "fairness.json"
    impact_path = tmp_path / "impact.json"
    fairness_path.write_text(json.dumps({"synthetic": True, "overall_test_metrics": {"false_positive_rate": 0.02}}), encoding="utf-8")
    impact_path.write_text(json.dumps({"synthetic": True, "overall": {"false_positive_count": 2}}), encoding="utf-8")
    monkeypatch.setattr(metrics_route, "FAIRNESS_METRICS_PATH", fairness_path)
    monkeypatch.setattr(metrics_route, "FALSE_POSITIVE_IMPACT_PATH", impact_path)
    client = _api_client(tmp_path, monkeypatch)
    try:
        monkeypatch.delenv("FLOWFREEZE_RBAC_TOKENS", raising=False)
        assert client.get("/api/metrics/fairness").status_code == 503
        config = {
            "analyst-token-with-more-than-32-characters-001": "fairness_analyst",
            "auditor-token-with-more-than-32-characters-002": "model_auditor",
            "ops-token-with-more-than-32-characters-00000003": "operations_viewer",
        }
        monkeypatch.setenv("FLOWFREEZE_RBAC_TOKENS", json.dumps(config))
        assert client.get("/api/metrics/fairness").status_code == 401
        assert client.get("/api/metrics/fairness", headers={"Authorization": "Bearer invalid-token-with-more-than-32-chars"}).status_code == 401
        ops = client.get("/api/metrics/fairness", headers={"Authorization": f"Bearer {next(key for key, role in config.items() if role == 'operations_viewer')}"})
        assert ops.status_code == 403
        headers = {"Authorization": f"Bearer {next(key for key, role in config.items() if role == 'fairness_analyst')}"}
        assert client.get("/api/metrics/fairness", headers=headers).json()["synthetic"] is True
        assert client.get("/api/metrics/false-positive-impact", headers=headers).json()["overall"]["false_positive_count"] == 2
    finally:
        client.close()


def test_fairness_api_rejects_identifier_bearing_artifact(tmp_path, monkeypatch):
    database = tmp_path / "fairness-api-identifiers.db"
    with sqlite3.connect(database) as connection:
        connection.executescript("CREATE TABLE incidents (incident_id TEXT); CREATE TABLE transactions (transaction_id TEXT); CREATE TABLE wallets (wallet_id TEXT);")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    monkeypatch.setenv("FLOWFREEZE_RBAC_TOKENS", json.dumps({"risk-admin-test-token-with-more-than-32-chars": "risk_admin"}))
    path = tmp_path / "unsafe.json"
    path.write_text(json.dumps({"synthetic": True, "wallet_id": "synthetic-example"}), encoding="utf-8")
    monkeypatch.setattr(metrics_route, "FAIRNESS_METRICS_PATH", path)
    with TestClient(app) as client:
        response = client.get("/api/metrics/fairness", headers={"Authorization": "Bearer risk-admin-test-token-with-more-than-32-chars"})
    assert response.status_code == 503
    assert "identifier" in response.json()["detail"]
