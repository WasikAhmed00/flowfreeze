from __future__ import annotations

from backend.db import application_connection
from backend.routes.decisions import create_analyst_feedback
from backend.schemas import AnalystFeedbackCreate
from data_generator.generate import generate_dataset
from core.shadow_mode import run_shadow_mode


def test_shadow_mode_is_synthetic_auditable_and_never_actuates(generated_fixture, tmp_path):
    output = tmp_path / "shadow.json"
    result = run_shadow_mode(generated_fixture["data_dir"], output)
    assert result["synthetic"] is True
    assert result["pilot_label"] == "SIMULATED — NOT PRODUCTION DATA"
    assert result["automatic_execution"] is False
    assert result["financial_actions_executed"] == 0
    assert result["cases_evaluated"] == len(result["events"]) > 0
    assert len({event["case_id"] for event in result["events"]}) == len(result["events"])
    assert all(result["event_schema"] == list(event.keys())[:len(result["event_schema"])] or set(result["event_schema"]) <= set(event) for event in result["events"])
    assert all(event["synthetic"] and event["automatic_execution"] is False for event in result["events"])
    assert all(event["financial_actions_executed"] == 0 for event in result["events"])
    assert all(event["estimated_exposure_difference_bdt"] == round(event["estimated_exposure_bdt"]-event["baseline_estimated_exposure_bdt"],2) for event in result["events"])
    assert all(event["decision_timestamp"] is None and event["actual_outcome"] is None for event in result["events"])
    assert all(event["case_id"].startswith("case_") for event in result["events"])
    assert output.is_file() and output.with_name("shadow_mode_events.csv").is_file()


def test_shadow_detection_metrics_calculate_from_events(generated_fixture):
    result = run_shadow_mode(generated_fixture["data_dir"])
    events = result["events"]
    # The published metrics use the simulator's generated-label evaluation; verify
    # output is bounded and event false-positive/negative flags reconcile to counts.
    assert 0 <= result["flowfreeze_shadow"]["precision"] <= 1
    assert 0 <= result["flowfreeze_shadow"]["recall"] <= 1
    assert result["flowfreeze_shadow"]["false_positives"] == sum(event["false_positive"] for event in events)
    assert result["flowfreeze_shadow"]["false_negatives"] == sum(event["false_negative"] for event in events)
    tp = result["flowfreeze_shadow"]["true_positives"]
    fp = result["flowfreeze_shadow"]["false_positives"]
    fn = result["flowfreeze_shadow"]["false_negatives"]
    assert result["flowfreeze_shadow"]["precision"] == round(tp / (tp + fp), 4)
    assert result["flowfreeze_shadow"]["recall"] == round(tp / (tp + fn), 4)
    assert result["flowfreeze_shadow"]["pr_auc_average_precision"] is None or 0 <= result["flowfreeze_shadow"]["pr_auc_average_precision"] <= 1
    assert result["human"]["analyst_agreement_rate"] is None
    assert all(item["target"] is None for item in result["business_success_targets"]["targets"].values())
    assert result["investigation"]["estimated_time_saved_minutes"] == round(
        result["current_process"]["synthetic_workload_minutes"]-result["investigation"]["synthetic_analyst_workload_minutes"], 2
    )


def test_feedback_endpoint_captures_auditable_feedback(generated_fixture, monkeypatch):
    database = generated_fixture["database"]
    with application_connection(database) as db:
        db.execute(
            "INSERT INTO analyst_decisions (incident_id, scenario_id, wallet_id, decision, proposed_amount_bdt, reason, actor, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("INC-TEST", "SCN-TEST", "WALLET-TEST", "approve", "100.00", "test", "analyst", "2026-01-01T00:00:00+00:00"),
        )
        decision_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    import backend.routes.decisions as route
    monkeypatch.setattr(route, "application_connection", lambda: application_connection(database))
    payload = AnalystFeedbackCreate(was_useful="partially", recommendation_feedback="helpful", trace_accuracy="partially_accurate", confidence="medium", reason="Trace mostly matched evidence.", actor="analyst")
    result = create_analyst_feedback(decision_id, payload)
    assert result["synthetic"] is True
    assert result["append_only"] is True
    assert result["was_useful"] == "partially"
    with application_connection(database) as db:
        row = db.execute("SELECT * FROM analyst_feedback WHERE decision_id = ?", (decision_id,)).fetchone()
        assert row["reason"] == "Trace mostly matched evidence."
        assert row["synthetic"] == 1
        try:
            db.execute("UPDATE analyst_feedback SET reason = 'changed' WHERE decision_id = ?", (decision_id,))
        except Exception as exc:
            assert "append-only" in str(exc)
        else:
            raise AssertionError("Feedback row must reject edits")


def test_shadow_metrics_api_includes_simulation_and_feedback_schema(monkeypatch, tmp_path):
    data_dir = tmp_path / "api_data"
    generate_dataset(data_dir, seed=7, cases_per_scenario=3)
    database = data_dir / "flowfreeze.db"
    import backend.routes.metrics as route
    monkeypatch.setattr(route, "application_connection", lambda: application_connection(database))
    result = route.get_shadow_mode()
    assert result["synthetic"] is True
    assert result["automatic_execution"] is False
    assert result["financial_actions_executed"] == 0
    assert result["feedback_summary"]["feedback_records"] == 0
    assert result["feedback_summary"]["analyst_agreement_rate"] is None
    assert "false_positives" in result["flowfreeze_shadow"]
    assert result["business_success_targets"]["status"] == "TARGET TO BE AGREED DURING PILOT"
