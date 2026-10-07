from __future__ import annotations

import csv
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.encoders import jsonable_encoder

from backend.routes.metrics import get_scenario_impact
from core.graph import trace_downstream
from core.impact_analysis import _unique_trace_events, analyze_scenario_impact, run_impact_analysis
from core.simulator import ReplayResult, TransactionEvent, TransactionSimulator


def test_direct_recipient_and_multi_hop_exposure_are_comparable(generated_fixture):
    scenario = "SCN-03-MULTIHOP-0001"
    impact = analyze_scenario_impact(scenario, generated_fixture["database"])
    direct = impact["comparison"]["direct_recipient_only"]
    traced = impact["comparison"]["flowfreeze_multi_hop"]

    assert impact["synthetic"] is True
    assert direct["wallets_identified"] == 1
    assert traced["wallets_identified"] > direct["wallets_identified"]
    assert traced["maximum_downstream_depth"] >= 1
    assert Decimal(traced["potentially_tainted_value_identified_bdt"]) > Decimal(
        direct["potentially_tainted_value_identified_bdt"]
    )
    assert Decimal(impact["comparison"]["missed_exposure_bdt"]) == (
        Decimal(traced["potentially_tainted_value_identified_bdt"])
        - Decimal(direct["potentially_tainted_value_identified_bdt"])
    )
    assert Decimal(impact["total_potentially_exposed_value_bdt"]) <= Decimal(
        impact["reported_amount_bdt"]
    )


def test_trace_transaction_value_is_deduplicated_by_event_id(generated_fixture):
    scenario = "SCN-02-FANOUT-0001"
    database = generated_fixture["database"]
    replay = TransactionSimulator(database).replay(scenario)
    trace = trace_downstream(replay)
    report_id = str(replay.incident["reported_transaction_id"])
    unique_ids = {report_id, *(edge.transaction_id for path in trace.paths for edge in path.edges)}
    event_by_id = {event.transaction_id: event for event in replay.transactions}
    expected = sum(event_by_id[transaction_id].amount for transaction_id in unique_ids)

    impact = analyze_scenario_impact(scenario, database)
    actual = impact["comparison"]["flowfreeze_multi_hop"]["unique_transaction_value_examined_bdt"]
    assert Decimal(actual) == Decimal(expected)
    duplicate_path_trace = replace(trace, paths=trace.paths + trace.paths)
    deduped = _unique_trace_events(duplicate_path_trace)
    assert len(deduped) == len({edge.transaction_id for path in trace.paths for edge in path.edges})
    assert sum(edge.amount_bdt for edge in deduped.values()) == sum(
        edge.amount_bdt for edge in _unique_trace_events(trace).values()
    )


def test_graph_trace_never_follows_a_transfer_backwards_in_time():
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)

    def event(transaction_id: str, minute: int, sender: str, receiver: str, kind: str = "transfer"):
        timestamp = start + timedelta(minutes=minute)
        return TransactionEvent(
            transaction_id=transaction_id,
            timestamp=timestamp,
            sender_wallet=sender,
            receiver_wallet=receiver,
            amount=100,
            transaction_type=kind,
            channel="agent" if kind == "cashout" else "app",
            agent_id=None,
            scenario_id="TEMPORAL-REGRESSION",
            sender_balance_before=200,
            sender_balance_after=100,
            receiver_balance_before=0,
            receiver_balance_after=100,
        )

    replay = ReplayResult(
        scenario_id="TEMPORAL-REGRESSION",
        incident={
            "incident_id": "INC-TEMPORAL-REGRESSION",
            "reported_transaction_id": "reported",
            "reported_at": start.isoformat(),
        },
        as_of=start + timedelta(minutes=10),
        initial_balances={},
        final_balances={},
        wallet_types={
            "victim": "individual",
            "W1": "individual",
            "W2": "individual",
            "impossible": "individual",
            "W3": "individual",
            "W4": "individual",
            "cash": "cash_destination",
        },
        transactions=(
            event("reported", 0, "victim", "W1"),
            event("to-W2", 2, "W1", "W2"),
            event("backwards", 1, "W2", "impossible"),
            event("invalid-cashout", 3, "impossible", "cash", "cashout"),
            event("to-W4", 3, "W2", "W4"),
            event("valid-cashout", 4, "W4", "cash", "cashout"),
        ),
        cashouts=(),
        snapshots=(),
    )

    trace = trace_downstream(replay, time_window_minutes=10)
    assert all(path.wallet_ids != ("W1", "W2", "impossible", "cash") for path in trace.paths)
    assert any(path.wallet_ids == ("W1", "W2", "W4", "cash") and path.terminal_cashout for path in trace.paths)
    for path in trace.paths:
        times = [edge.timestamp for edge in path.edges]
        assert times == sorted(times)


def test_delay_analysis_uses_generated_event_timestamps_and_tracks_cashouts(generated_fixture):
    scenario = "SCN-06-FANOUT-CASHOUT-0006"
    impact = analyze_scenario_impact(scenario, generated_fixture["database"])
    curve = impact["response_delay_curve"]

    assert [row["delay_minutes"] for row in curve] == [0, 5, 10, 15, 30, 60]
    assert all(row["synthetic"] is True for row in curve)
    assert curve[0]["cashout_events_before_intervention"] == 0
    assert curve[1]["cashout_events_before_intervention"] >= 1
    assert curve[0]["downstream_wallets_identified"] == 0
    assert curve[-1]["downstream_wallets_identified"] >= curve[1]["downstream_wallets_identified"]
    assert curve[-1]["comparison"]["flowfreeze_multi_hop"]["wallets_identified"] >= 1
    assert curve[-1]["representative_paths"]
    assert Decimal(curve[-1]["comparison"]["missed_exposure_bdt"]) >= 0
    assert any(
        path["terminal_cashout"] and len(path["edges"]) >= 4
        for path in curve[-1]["representative_paths"]
    )
    for row in curve:
        assert Decimal(row["estimated_exposure_remaining_bdt"]) + Decimal(
            row["estimated_exposure_already_cashed_out_bdt"]
        ) == Decimal(row["estimated_total_potentially_exposed_bdt"])
        assert Decimal(row["estimated_total_potentially_exposed_bdt"]) <= Decimal(
            impact["reported_amount_bdt"]
        )


def test_impact_artifact_labels_synthetic_and_writes_csv(generated_fixture, tmp_path):
    output_json = tmp_path / "impact_analysis.json"
    output_csv = tmp_path / "impact_analysis.csv"
    result = run_impact_analysis(
        generated_fixture["database"],
        output_json,
        output_csv,
        delay_windows_minutes=(0, 5),
    )

    assert result["synthetic_data"] is True
    assert result["case_count"] > 0
    assert result["aggregate_metrics"]["missed_exposure_bdt"] is not None
    assert [row["delay_minutes"] for row in result["response_delay_metrics"]] == [0, 5]
    saved = json.loads(output_json.read_text(encoding="utf-8"))
    assert saved["dataset_assumptions"]["scenario_count"] == result["case_count"]
    assert saved["limitations"]
    with output_csv.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == result["case_count"]
    assert "delay_0m_estimated_exposure_remaining_bdt" in rows[0]


def test_impact_route_returns_json_compatible_synthetic_payload(generated_fixture, monkeypatch):
    scenario = "SCN-02-FANOUT-0001"
    expected = analyze_scenario_impact(scenario, generated_fixture["database"])
    monkeypatch.setattr(
        "core.impact_analysis.analyze_scenario_impact",
        lambda scenario_id: expected if scenario_id == scenario else None,
    )

    response = jsonable_encoder(get_scenario_impact(scenario))
    assert response["synthetic"] is True
    assert response["scenario_id"] == scenario
    assert set(response["comparison"]) >= {
        "direct_recipient_only",
        "flowfreeze_multi_hop",
        "missed_exposure_bdt",
    }
    assert response["response_delay_curve"][0]["delay_minutes"] == 0
