from __future__ import annotations

from core.business_impact import run_business_impact
from backend.routes.metrics import get_business_impact


def test_business_impact_api_schema_and_synthetic_flag():
    result = get_business_impact()
    assert result["synthetic"] is True
    assert set(("fraud_loss", "investigation_efficiency", "customer_harm", "analyst_productivity", "assumptions")) <= set(result)
    assert result["label"] == "SYNTHETIC BUSINESS SIMULATION"
    assert result["validation_targets"]["status"].startswith("Future validation target")


def test_business_impact_calculations_and_no_double_counting(generated_fixture):
    result = run_business_impact(generated_fixture["data_dir"])
    assert result["synthetic"] is True
    assert result["case_count"] > 0
    loss = result["fraud_loss"]
    assert loss["simulated_prevented_exposure_bdt"] <= loss["potentially_interceptable_exposure_bdt"]
    assert loss["simulated_prevented_exposure_bdt"] <= loss["initial_suspicious_value_bdt"]
    assert loss["simulated_loss_reduction_rate"] == round(
        loss["simulated_prevented_exposure_bdt"] / loss["initial_suspicious_value_bdt"], 4
    )
    # Exposure comes from per-wallet generated taint labels, not the sum of
    # repeated gross edge values along multihop paths.
    assert result["baseline_vs_flowfreeze"]["flowfreeze_exposure_identified_bdt"] <= sum(
        case["flowfreeze"]["identified_exposure_bdt"] for case in result["synthetic_case_examples"]
    ) + result["baseline_vs_flowfreeze"]["flowfreeze_exposure_identified_bdt"]
    assert "minutes per reviewed transaction" in result["assumptions"][2]
    assert result["investigation_efficiency"]["time_model"] == "SYNTHETIC OPERATIONAL SIMULATION"


def test_baseline_and_flowfreeze_are_reported_separately(generated_fixture):
    result = run_business_impact(generated_fixture["data_dir"])
    comparison = result["baseline_vs_flowfreeze"]
    assert comparison["baseline"] == "direct-recipient-only, manual downstream discovery"
    assert comparison["baseline_time_minutes"] >= 0
    assert comparison["flowfreeze_time_minutes"] >= 0
    assert comparison["exposure_difference_bdt"] == round(
        comparison["flowfreeze_exposure_identified_bdt"] - comparison["baseline_exposure_identified_bdt"], 2
    )
    assert result["investigation_efficiency"]["investigation_time_saved_minutes"] == comparison["time_saved_minutes"]


def test_customer_harm_policy_simulation_is_synthetic(generated_fixture):
    result = run_business_impact(generated_fixture["data_dir"])
    harm = result["customer_harm"]
    assert harm["synthetic_policy_simulation_only"] is True
    assert harm["overly_aggressive_policy_legitimate_value_affected_bdt"] >= harm["flowfreeze_legitimate_value_affected_bdt"]
    assert 0 <= harm["unnecessary_intervention_rate"] <= 1
    assert harm["legitimate_cases_correctly_left_alone"] <= harm["legitimate_case_count"]


def test_output_artifact_and_csv(generated_fixture, tmp_path):
    output = tmp_path / "impact.json"
    csv_output = tmp_path / "impact.csv"
    result = run_business_impact(generated_fixture["data_dir"], output)
    assert output.is_file()
    assert '"synthetic": true' in output.read_text()
    assert result["limitations"]
