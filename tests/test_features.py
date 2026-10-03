from __future__ import annotations

from ml.features import FEATURE_COLUMNS, build_decision_features, build_feature_table


def test_feature_columns_are_complete_and_leakage_aware(generated_fixture):
    decision_features = build_decision_features(generated_fixture["data_dir"])
    training_table = build_feature_table(generated_fixture["data_dir"])

    expected = {
        "account_age_days",
        "opening_balance_bdt",
        "profile_average_transaction_bdt",
        "profile_frequency_per_day",
        "reported_amount_bdt",
        "amount_to_profile_average_ratio",
        "report_to_analysis_seconds",
        "reported_sender",
        "reported_recipient",
        "observed_incoming_count",
        "observed_outgoing_count",
        "observed_transaction_count",
        "observed_incoming_amount_bdt",
        "observed_outgoing_amount_bdt",
        "observed_net_flow_bdt",
        "observed_average_outgoing_bdt",
        "observed_max_outgoing_bdt",
        "observed_cashout_count",
        "post_report_incoming_count",
        "post_report_outgoing_count",
        "post_report_outgoing_amount_bdt",
        "post_report_cashout_count",
        "merchant_payment_count",
        "distinct_counterparties",
        "graph_hops_from_reported_recipient",
        "reachable_from_reported_recipient",
        "customer_type",
        "normal_active_hours",
        "usual_transaction_types",
        "incident_type",
    }

    assert expected.issubset(decision_features.columns)
    assert set(FEATURE_COLUMNS) == expected
    assert set(FEATURE_COLUMNS).issubset(training_table.columns)
    assert not {"scenario_id", "wallet_id", "split", "fraud_flag", "expected_next_action"}.intersection(FEATURE_COLUMNS)
    assert not decision_features[FEATURE_COLUMNS].isna().all(axis=1).any()
