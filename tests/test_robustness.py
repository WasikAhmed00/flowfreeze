from __future__ import annotations

from ml.robustness import run_robustness


def test_robustness_checks_are_reported(generated_fixture):
    result = run_robustness(
        generated_fixture["data_dir"], generated_fixture["artifact_dir"], seed=42, bootstrap_reps=10
    )
    assert result["synthetic_only"] is True
    assert "prevalence_baseline" in result
    assert "behavior_rule_baseline" in result
    assert "shuffled_label_check" in result
    assert len(result["scenario_cluster_bootstrap"]["ci95"]) == 2
    assert result["leave_one_family_out"]
