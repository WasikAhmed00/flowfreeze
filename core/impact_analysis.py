"""Synthetic-only financial exposure and response-delay analysis.

All amounts in this module are estimates derived from the generated transaction
ledger and the proportional attribution in ``core.taint``. They are not actual
financial loss, customer impact, recoveries, or production performance.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any, Iterable

from backend.db import DEFAULT_DATABASE_PATH, connect_database
from core.graph import TraceResult, trace_downstream
from core.intervention import load_policy
from core.simulator import ReplayResult, TransactionEvent, TransactionSimulator
from core.taint import TaintResult, calculate_proportional_taint

CENT = Decimal("0.01")
DEFAULT_DELAY_WINDOWS_MINUTES = (0, 5, 10, 15, 30, 60)
DEFAULT_JSON_PATH = Path(__file__).resolve().parents[1] / "ml" / "artifacts" / "impact_analysis.json"
DEFAULT_CSV_PATH = Path(__file__).resolve().parents[1] / "ml" / "artifacts" / "impact_analysis.csv"


def _money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_DOWN)


def _iso_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Incident and transaction timestamps must include a timezone.")
    return parsed.astimezone(timezone.utc)


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.quantize(CENT, rounding=ROUND_DOWN), "f")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    return value


def _unique_trace_events(trace: TraceResult) -> dict[str, Any]:
    """Deduplicate path-expanded graph edges by transaction ID."""
    return {
        edge.transaction_id: edge
        for path in trace.paths
        for edge in path.edges
    }


def _wallet_depths(trace: TraceResult, digital_wallet_ids: set[str] | None = None) -> dict[str, int]:
    """Return shortest depth to downstream digital wallets, excluding cash-out destinations."""
    depths: dict[str, int] = {}
    for path in trace.paths:
        for depth, wallet_id in enumerate(path.wallet_ids[1:], start=1):
            if digital_wallet_ids is not None and wallet_id not in digital_wallet_ids:
                continue
            current = depths.get(wallet_id)
            if current is None or depth < current:
                depths[wallet_id] = depth
    return depths


def _strategy_metrics(
    *,
    wallet_ids: set[str],
    trace_events: dict[str, Any],
    reported_event: TransactionEvent,
    taint: TaintResult,
    traced_cashouts: list[Any],
    traced_cashout_ids: set[str],
    event_by_id: dict[str, TransactionEvent],
    all_digital_wallet_count: int,
    policy_cap: Decimal,
    downstream_hops: int,
    max_hops: int,
) -> dict[str, Any]:
    wallets = {wallet.wallet_id: wallet for wallet in taint.wallets}
    selected_wallets = [wallets[wallet_id] for wallet_id in wallet_ids if wallet_id in wallets]
    selected_cashouts = [
        item for item in traced_cashouts
        if item.wallet_id in wallet_ids and item.transaction_id in traced_cashout_ids
    ]
    remaining_taint = sum((wallet.potentially_tainted_bdt for wallet in selected_wallets), Decimal("0.00"))
    exited_taint = sum((item.potentially_tainted_bdt for item in selected_cashouts), Decimal("0.00"))
    exposure = remaining_taint + exited_taint
    cashout_gross = sum((item.gross_cashout_bdt for item in selected_cashouts), Decimal("0.00"))
    legitimate_at_risk = sum(
        (
            max(
                Decimal("0.00"),
                min(wallet.balance_bdt, policy_cap) - wallet.potentially_tainted_bdt,
            )
            for wallet in selected_wallets
        ),
        Decimal("0.00"),
    )

    # A strategy examines unique ledger events, not one copy per graph path.
    transaction_ids = {reported_event.transaction_id}
    transaction_ids.update(
        transaction_id
        for transaction_id, edge in trace_events.items()
        if edge.sender_wallet in wallet_ids
    )
    transaction_value = sum(
        (Decimal(event_by_id[transaction_id].amount) for transaction_id in transaction_ids if transaction_id in event_by_id),
        Decimal("0.00"),
    )
    identified_count = len({wallet_id for wallet_id in wallet_ids if wallet_id in wallets})

    return {
        "wallets_identified": identified_count,
        "downstream_wallets_identified": max(0, identified_count - 1),
        "downstream_hops_identified": downstream_hops,
        "maximum_downstream_depth": max_hops,
        "investigation_breadth_ratio": round(identified_count / all_digital_wallet_count, 6) if all_digital_wallet_count else 0.0,
        "potentially_tainted_value_identified_bdt": _money(exposure),
        "remaining_potentially_tainted_value_bdt": _money(remaining_taint),
        "already_cashed_out_potentially_tainted_value_bdt": _money(exited_taint),
        "cashouts_identified": len(selected_cashouts),
        "gross_cashout_value_examined_bdt": _money(cashout_gross),
        "unique_transaction_value_examined_bdt": _money(transaction_value),
        "potentially_legitimate_value_at_risk_bdt": _money(legitimate_at_risk),
        "assumption_for_legitimate_value_at_risk": (
            "Illustrative cap scenario: apply min(current wallet balance, configured per-wallet policy cap) "
            "to every identified wallet; subtract estimated taint. This is not a policy recommendation or action."
        ),
    }


def _representative_paths(
    trace: TraceResult,
    taint: TaintResult,
    reported_event: TransactionEvent,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Select a few longest real trace paths for a judge-friendly case view."""
    movement_by_id = {item.transaction_id: item for item in taint.movements}
    paths = sorted(
        trace.paths,
        key=lambda item: (-len(item.edges), tuple(edge.transaction_id for edge in item.edges)),
    )[:limit]
    return [
        {
            "wallet_ids": list(path.wallet_ids),
            "terminal_cashout": path.terminal_cashout,
            "edges": [
                {
                    "transaction_id": edge.transaction_id,
                    "from_wallet": edge.sender_wallet,
                    "to_wallet": edge.receiver_wallet,
                    "timestamp": edge.timestamp,
                    "gross_amount_bdt": edge.amount_bdt,
                    "potentially_tainted_bdt": movement_by_id.get(edge.transaction_id).potentially_tainted_bdt
                    if edge.transaction_id in movement_by_id else Decimal("0.00"),
                    "transaction_type": edge.transaction_type,
                    "cashout": edge.is_cashout,
                }
                for edge in path.edges
            ],
        }
        for path in paths
    ]


def analyze_replay_impact(
    replay: ReplayResult,
    *,
    delay_windows_minutes: Iterable[int] = DEFAULT_DELAY_WINDOWS_MINUTES,
) -> dict[str, Any]:
    """Compare direct-recipient-only and graph-traced evidence for one snapshot."""
    trace = trace_downstream(replay)
    taint = calculate_proportional_taint(replay)
    reported_id = str(replay.incident["reported_transaction_id"])
    reported_event = next((item for item in replay.transactions if item.transaction_id == reported_id), None)
    if reported_event is None:
        raise ValueError("Replay does not contain its referenced reported transaction.")
    direct_wallet = reported_event.receiver_wallet
    trace_events = _unique_trace_events(trace)
    digital_wallet_ids = {wallet.wallet_id for wallet in taint.wallets}
    depths = _wallet_depths(trace, digital_wallet_ids)
    traced_wallet_ids = {direct_wallet, *trace.downstream_wallet_ids}
    direct_wallet_ids = {direct_wallet}
    cashouts = list(taint.cashouts)
    traced_cashout_ids = {item.transaction_id for item in trace.cashouts}
    event_by_id = {event.transaction_id: event for event in replay.transactions}
    policy_cap = _money(load_policy()["maximum_simulated_hold_bdt"])
    all_digital_count = len(taint.wallets)
    max_hops = max(depths.values(), default=0)

    direct = _strategy_metrics(
        wallet_ids=direct_wallet_ids,
        trace_events=trace_events,
        reported_event=reported_event,
        taint=taint,
        traced_cashouts=cashouts,
        traced_cashout_ids=traced_cashout_ids,
        event_by_id=event_by_id,
        all_digital_wallet_count=all_digital_count,
        policy_cap=policy_cap,
        downstream_hops=0,
        max_hops=0,
    )
    network = _strategy_metrics(
        wallet_ids=traced_wallet_ids,
        trace_events=trace_events,
        reported_event=reported_event,
        taint=taint,
        traced_cashouts=cashouts,
        traced_cashout_ids=traced_cashout_ids,
        event_by_id=event_by_id,
        all_digital_wallet_count=all_digital_count,
        policy_cap=policy_cap,
        downstream_hops=sum(1 for edge in trace_events.values() if not edge.is_cashout),
        max_hops=max_hops,
    )

    total_exposure = _money(
        taint.remaining_potentially_tainted_bdt + taint.cashed_out_potentially_tainted_bdt
    )
    direct_exposure = _money(direct["potentially_tainted_value_identified_bdt"])
    network_exposure = _money(network["potentially_tainted_value_identified_bdt"])
    missed = max(Decimal("0.00"), network_exposure - direct_exposure)
    all_wallets = {wallet.wallet_id: wallet for wallet in taint.wallets}
    downstream_value = sum(
        (Decimal(edge.amount_bdt) for edge in trace_events.values()), Decimal("0.00")
    )
    delay_curve = []
    for delay in sorted(set(int(value) for value in delay_windows_minutes)):
        if delay < 0:
            raise ValueError("Delay windows must be non-negative integers.")
        cutoff = _iso_datetime(str(replay.incident["reported_at"])) + timedelta(minutes=delay)
        if cutoff > replay.as_of:
            # A given replay cannot truthfully report outcomes after its cutoff.
            delay_curve.append({
                "delay_minutes": delay,
                "available_in_this_snapshot": False,
                "as_of": cutoff,
                "note": "Snapshot is later than this replay's as_of time; use the full response-delay endpoint.",
            })
        else:
            delay_curve.append({
                "delay_minutes": delay,
                "available_in_this_snapshot": delay == 0,
                "as_of": cutoff,
                "note": "Per-delay ledger replays are provided by analyze_scenario_impact().",
            })

    return _json_ready({
        "synthetic": True,
        "scenario_id": replay.scenario_id,
        "incident_id": str(replay.incident["incident_id"]),
        "as_of": replay.as_of,
        "reported_at": _iso_datetime(str(replay.incident["reported_at"])),
        "source_wallet_id": reported_event.sender_wallet,
        "direct_recipient_wallet_id": direct_wallet,
        "reported_amount_bdt": _money(replay.incident["reported_amount"]),
        "total_potentially_exposed_value_bdt": total_exposure,
        "remaining_potentially_tainted_value_bdt": taint.remaining_potentially_tainted_bdt,
        "already_cashed_out_potentially_tainted_value_bdt": taint.cashed_out_potentially_tainted_bdt,
        "unattributed_reported_value_bdt": taint.unattributed_bdt,
        "comparison": {
            "direct_recipient_only": direct,
            "flowfreeze_multi_hop": network,
            "missed_exposure_bdt": missed,
            "additional_exposure_identified_by_multi_hop_bdt": missed,
            "exposure_recovery_rate": round(float(network_exposure / total_exposure), 6) if total_exposure else 0.0,
            "direct_only_coverage_of_traced_exposure_rate": round(float(direct_exposure / network_exposure), 6) if network_exposure else 0.0,
        },
        "graph": {
            "trace_window_minutes": trace.limits.time_window_minutes,
            "hop_limit": trace.limits.hop_limit,
            "truncated": trace.limits.truncated,
            "downstream_wallet_ids": list(trace.downstream_wallet_ids),
            "representative_paths": _representative_paths(trace, taint, reported_event),
            "downstream_unique_gross_transaction_value_bdt": _money(downstream_value),
        },
        "methodology": {
            "potentially_exposed_value": "Remaining proportional taint in digital wallets plus proportional taint attributed to observed cash-outs; a ledger estimate, not financial loss.",
            "direct_recipient_only": "The direct recipient plus its unique post-report outgoing graph events and directly attributable cash-outs within the observed trace window.",
            "flowfreeze_multi_hop": "The direct recipient plus graph-reachable downstream wallets/events within the same trace window; each transaction is counted once by transaction_id.",
            "missed_exposure": "max(0, flowfreeze_multi_hop potentially tainted value identified - direct-recipient-only value identified).",
            "exposure_recovery_rate": "FlowFreeze multi-hop potentially tainted value identified divided by total currently remaining plus already-cashed-out estimated taint; 0 when denominator is 0.",
            "transaction_value": "Sum of gross amounts of unique transaction IDs examined; this is transaction volume, not unique underlying funds.",
            "legitimate_value_at_risk": "Illustrative configured-cap scenario in each strategy; not an intervention recommendation or observed customer impact.",
        },
        "response_delay_curve": delay_curve,
        "limitations": [
            "All data and values are synthetic and do not describe upay BD customers, losses, workflows, or operating performance.",
            "Proportional taint is an accounting assumption, not ground-truth financial loss, ownership, or recoverability.",
            "Generated event times are not actual response or investigation delays.",
            "Gross value across distinct hops may represent the same underlying funds again; transaction values are deduplicated by event, not by economic source.",
            "Any simulated prevented exposure would require an explicit immediate-intervention counterfactual and is not observed loss prevention.",
        ],
    })


def analyze_scenario_impact(
    scenario_id: str,
    database_path: str | Path | None = None,
    *,
    delay_windows_minutes: Iterable[int] = DEFAULT_DELAY_WINDOWS_MINUTES,
) -> dict[str, Any]:
    """Return actual-ledger case comparison and replay-derived delay snapshots."""
    simulator = TransactionSimulator(database_path)
    delays = tuple(sorted(set(int(value) for value in delay_windows_minutes)))
    if any(value < 0 for value in delays):
        raise ValueError("Delay windows must be non-negative integers.")
    with closing(connect_database(database_path)) as connection:
        base_replay = simulator.replay(scenario_id, connection=connection)
        base = analyze_replay_impact(base_replay, delay_windows_minutes=delays)
        report_time = _iso_datetime(str(base_replay.incident["reported_at"]))
        delay_rows = []
        for delay in delays:
            cutoff = report_time + timedelta(minutes=delay)
            replay = simulator.replay(scenario_id, cutoff, connection=connection)
            snapshot = analyze_replay_impact(replay, delay_windows_minutes=())
            delay_rows.append(_delay_snapshot(replay, delay, snapshot=snapshot, include_paths=True))
    base["response_delay_curve"] = delay_rows
    return _json_ready(base)


def _delay_snapshot(
    replay: ReplayResult,
    delay: int,
    *,
    snapshot: dict[str, Any] | None = None,
    include_paths: bool = False,
) -> dict[str, Any]:
    trace = trace_downstream(replay, time_window_minutes=60)
    taint = calculate_proportional_taint(replay)
    unique_edges = _unique_trace_events(trace)
    wallet_ids = {trace.source_wallet, *trace.downstream_wallet_ids}
    cashouts = [item for item in trace.cashouts if item.wallet_id in wallet_ids]
    digital_wallet_ids = {wallet.wallet_id for wallet in taint.wallets}
    depths = _wallet_depths(trace, digital_wallet_ids)
    remaining = _money(taint.remaining_potentially_tainted_bdt)
    cashed_out = _money(taint.cashed_out_potentially_tainted_bdt)
    gross_downstream = sum((Decimal(edge.amount_bdt) for edge in unique_edges.values()), Decimal("0.00"))
    result = {
        "delay_minutes": delay,
        "as_of": replay.as_of,
        "cumulative_downstream_transaction_value_bdt": _money(gross_downstream),
        "cumulative_potentially_tainted_value_bdt": _money(remaining + cashed_out),
        "downstream_wallets_identified": len(trace.downstream_wallet_ids),
        "wallets_identified_including_direct_recipient": len(wallet_ids),
        "maximum_downstream_hops_identified": max(depths.values(), default=0),
        "cashout_events_before_intervention": len(cashouts),
        "gross_cashout_value_before_intervention_bdt": _money(sum((Decimal(item.amount_bdt) for item in cashouts), Decimal("0.00"))),
        "estimated_exposure_remaining_bdt": remaining,
        "estimated_exposure_already_cashed_out_bdt": cashed_out,
        "estimated_total_potentially_exposed_bdt": _money(remaining + cashed_out),
        "synthetic": True,
    }
    if snapshot is not None:
        comparison = snapshot["comparison"]
        direct = comparison["direct_recipient_only"]
        network = comparison["flowfreeze_multi_hop"]
        result["comparison"] = {
            "direct_recipient_only": direct,
            "flowfreeze_multi_hop": network,
            "missed_exposure_bdt": comparison["missed_exposure_bdt"],
        }
        if include_paths:
            result["representative_paths"] = snapshot["graph"]["representative_paths"]
            result["trace_truncated"] = snapshot["graph"]["truncated"]
    return _json_ready(result)


def _aggregate_delay_curves(case_curves: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    if not case_curves:
        return []
    by_delay: dict[int, list[dict[str, Any]]] = {}
    for curve in case_curves:
        for row in curve:
            by_delay.setdefault(int(row["delay_minutes"]), []).append(row)
    result = []
    money_fields = (
        "cumulative_downstream_transaction_value_bdt",
        "cumulative_potentially_tainted_value_bdt",
        "gross_cashout_value_before_intervention_bdt",
        "estimated_exposure_remaining_bdt",
        "estimated_exposure_already_cashed_out_bdt",
        "estimated_total_potentially_exposed_bdt",
    )
    count_fields = (
        "downstream_wallets_identified",
        "wallets_identified_including_direct_recipient",
        "maximum_downstream_hops_identified",
        "cashout_events_before_intervention",
    )
    for delay in sorted(by_delay):
        items = by_delay[delay]
        aggregate: dict[str, Any] = {
            "delay_minutes": delay,
            "scenario_count": len(items),
            "synthetic": True,
        }
        for field in money_fields:
            aggregate[field] = _money(sum((Decimal(str(item[field])) for item in items), Decimal("0.00")))
            aggregate[f"average_{field}_per_scenario_bdt"] = _money(aggregate[field] / len(items))
        for field in count_fields:
            aggregate[f"total_{field}"] = sum(int(item[field]) for item in items)
            aggregate[f"average_{field}_per_scenario"] = round(aggregate[f"total_{field}"] / len(items), 4)
        result.append(aggregate)
    return result


def _ratio(numerator: Decimal, denominator: Decimal) -> float:
    return round(float(numerator / denominator), 6) if denominator else 0.0


def run_impact_analysis(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    output_json: str | Path = DEFAULT_JSON_PATH,
    output_csv: str | Path = DEFAULT_CSV_PATH,
    *,
    delay_windows_minutes: Iterable[int] = DEFAULT_DELAY_WINDOWS_MINUTES,
) -> dict[str, Any]:
    """Compute deterministic aggregate impact and response-delay metrics."""
    delays = tuple(sorted(set(int(value) for value in delay_windows_minutes)))
    if any(value < 0 for value in delays):
        raise ValueError("Delay windows must be non-negative integers.")
    case_rows: list[dict[str, Any]] = []
    delay_curves: list[list[dict[str, Any]]] = []
    simulator = TransactionSimulator(database_path)

    with closing(connect_database(database_path)) as connection:
        scenario_ids = [
            str(row[0]) for row in connection.execute(
                "SELECT scenario_id FROM incidents ORDER BY scenario_id"
            ).fetchall()
        ]
        if not scenario_ids:
            raise ValueError("No incidents found. Generate synthetic data before running impact analysis.")
        report_times = {
            str(row["scenario_id"]): str(row["reported_at"])
            for row in connection.execute("SELECT scenario_id, reported_at FROM incidents").fetchall()
        }
        policy_cap = _money(load_policy()["maximum_simulated_hold_bdt"])
        for scenario_id in scenario_ids:
            base_replay = simulator.replay(scenario_id, connection=connection)
            impact = analyze_replay_impact(base_replay, delay_windows_minutes=())
            comparison = impact["comparison"]
            direct = comparison["direct_recipient_only"]
            network = comparison["flowfreeze_multi_hop"]
            delay_rows = []
            report_time = _iso_datetime(report_times[scenario_id])
            for delay in delays:
                replay = simulator.replay(
                    scenario_id,
                    report_time + timedelta(minutes=delay),
                    connection=connection,
                )
                row = _delay_snapshot(replay, delay)
                delay_rows.append(row)
            delay_curves.append(delay_rows)
            case_row = {
                "scenario_id": scenario_id,
                "incident_id": impact["incident_id"],
                "as_of": impact["as_of"],
                "reported_amount_bdt": impact["reported_amount_bdt"],
                "total_potentially_exposed_value_bdt": impact["total_potentially_exposed_value_bdt"],
                "remaining_potentially_tainted_value_bdt": impact["remaining_potentially_tainted_value_bdt"],
                "already_cashed_out_potentially_tainted_value_bdt": impact["already_cashed_out_potentially_tainted_value_bdt"],
                "direct_recipient_exposure_bdt": direct["potentially_tainted_value_identified_bdt"],
                "multi_hop_exposure_bdt": network["potentially_tainted_value_identified_bdt"],
                "missed_exposure_bdt": comparison["missed_exposure_bdt"],
                "wallets_found_direct": direct["wallets_identified"],
                "wallets_found_traced": network["wallets_identified"],
                "downstream_wallets_found": network["downstream_wallets_identified"],
                "downstream_hops_found": network["downstream_hops_identified"],
                "cashouts_found_direct": direct["cashouts_identified"],
                "cashouts_found_traced": network["cashouts_identified"],
                "direct_transaction_value_examined_bdt": direct["unique_transaction_value_examined_bdt"],
                "traced_transaction_value_examined_bdt": network["unique_transaction_value_examined_bdt"],
                "potentially_legitimate_value_at_risk_direct_bdt": direct["potentially_legitimate_value_at_risk_bdt"],
                "potentially_legitimate_value_at_risk_traced_bdt": network["potentially_legitimate_value_at_risk_bdt"],
                "exposure_recovery_rate": comparison["exposure_recovery_rate"],
            }
            case_rows.append(case_row)

    def total(field: str) -> Decimal:
        return _money(sum((Decimal(str(row[field])) for row in case_rows), Decimal("0.00")))

    reported_total = total("reported_amount_bdt")
    exposure_total = total("total_potentially_exposed_value_bdt")
    direct_total = total("direct_recipient_exposure_bdt")
    network_total = total("multi_hop_exposure_bdt")
    missed_total = total("missed_exposure_bdt")
    scenarios = len(case_rows)
    aggregate = {
        "scenario_count": scenarios,
        "reported_suspicious_amount_bdt": reported_total,
        "total_potentially_exposed_value_bdt": exposure_total,
        "remaining_potentially_tainted_value_bdt": total("remaining_potentially_tainted_value_bdt"),
        "already_cashed_out_potentially_tainted_value_bdt": total("already_cashed_out_potentially_tainted_value_bdt"),
        "direct_recipient_exposure_bdt": direct_total,
        "multi_hop_exposure_bdt": network_total,
        "missed_exposure_bdt": missed_total,
        "additional_exposure_identified_by_multi_hop_bdt": missed_total,
        "exposure_recovery_rate": _ratio(network_total, exposure_total),
        "direct_only_coverage_of_traced_exposure_rate": _ratio(direct_total, network_total),
        "wallets_found_direct": sum(int(row["wallets_found_direct"]) for row in case_rows),
        "wallets_found_traced": sum(int(row["wallets_found_traced"]) for row in case_rows),
        "downstream_wallets_found": sum(int(row["downstream_wallets_found"]) for row in case_rows),
        "downstream_hops_found": sum(int(row["downstream_hops_found"]) for row in case_rows),
        "average_downstream_wallets_per_scenario": round(sum(int(row["downstream_wallets_found"]) for row in case_rows) / scenarios, 4),
        "cashouts_found_direct": sum(int(row["cashouts_found_direct"]) for row in case_rows),
        "cashouts_found_traced": sum(int(row["cashouts_found_traced"]) for row in case_rows),
        "direct_transaction_value_examined_bdt": total("direct_transaction_value_examined_bdt"),
        "traced_transaction_value_examined_bdt": total("traced_transaction_value_examined_bdt"),
        "potentially_legitimate_value_at_risk_direct_bdt": total("potentially_legitimate_value_at_risk_direct_bdt"),
        "potentially_legitimate_value_at_risk_traced_bdt": total("potentially_legitimate_value_at_risk_traced_bdt"),
        "illustrative_policy_cap_bdt_per_wallet": policy_cap,
    }
    result = {
        "synthetic_data": True,
        "dataset_assumptions": {
            "source": "Generated synthetic incidents and event-time transaction ledger in data/flowfreeze.db.",
            "scenario_count": scenarios,
            "analysis_snapshot": "The incident's generated analysis_at timestamp.",
            "trace_window_minutes": 30,
            "trace_hop_limit": 5,
            "response_delay_windows_minutes": list(delays),
            "money_arithmetic": "Existing ledger amounts are whole BDT; attributed amounts use Decimal and round down to poisha.",
            "exposure_definition": "Remaining proportional taint in digital wallets plus taint attributed to observed cash-outs; it is not financial loss.",
            "comparison_definition": "Both strategies use the same incident snapshot, 30-minute graph window, hop limit and proportional attribution. Direct-only considers the reported transaction's recipient; FlowFreeze considers that wallet and graph-reachable downstream wallets.",
            "missed_exposure_definition": "max(0, traced multi-hop potentially tainted value identified - direct-recipient-only potentially tainted value identified).",
            "transaction_volume_definition": "Sum gross values of unique transaction IDs examined; repeated underlying funds moving through separate hops can contribute again as transaction volume.",
            "legitimate_value_at_risk_assumption": "For every identified wallet, illustrate a hold at min(current balance, policy cap); subtract estimated taint. Not a recommendation or real action.",
            "simulated_prevented_exposure": "Not estimated in this aggregate report. Any counterfactual requires a stated intervention time and outcome assumptions; it is never observed prevention.",
        },
        "aggregate_metrics": aggregate,
        "direct_recipient_baseline_metrics": {
            "wallets_found_direct": aggregate["wallets_found_direct"],
            "direct_recipient_exposure_bdt": direct_total,
            "cashouts_found_direct": aggregate["cashouts_found_direct"],
            "transaction_value_examined_bdt": aggregate["direct_transaction_value_examined_bdt"],
            "potentially_legitimate_value_at_risk_bdt": aggregate["potentially_legitimate_value_at_risk_direct_bdt"],
        },
        "multi_hop_metrics": {
            "wallets_found_traced": aggregate["wallets_found_traced"],
            "downstream_wallets_found": aggregate["downstream_wallets_found"],
            "downstream_hops_found": aggregate["downstream_hops_found"],
            "multi_hop_exposure_bdt": network_total,
            "cashouts_found_traced": aggregate["cashouts_found_traced"],
            "transaction_value_examined_bdt": aggregate["traced_transaction_value_examined_bdt"],
            "potentially_legitimate_value_at_risk_bdt": aggregate["potentially_legitimate_value_at_risk_traced_bdt"],
        },
        "missed_exposure_metrics": {
            "missed_exposure_bdt": missed_total,
            "additional_exposure_identified_by_multi_hop_bdt": missed_total,
            "exposure_recovery_rate": aggregate["exposure_recovery_rate"],
            "direct_only_coverage_of_traced_exposure_rate": aggregate["direct_only_coverage_of_traced_exposure_rate"],
        },
        "response_delay_metrics": _aggregate_delay_curves(delay_curves),
        "case_count": scenarios,
        "limitations": [
            "This analysis uses generated synthetic cases only; it contains no actual fraud-loss or upay BD operational-delay data.",
            "Proportional taint is not ground-truth financial loss, ownership, recoverability, or proof of fraud.",
            "Response-delay windows are hypothetical offsets applied to generated transaction timestamps, not measured investigation response times.",
            "A transaction-value total is gross unique event volume, not a sum of unique economic funds across hops.",
            "Potentially legitimate value at risk uses an illustrative per-wallet cap scenario and does not represent a recommended or executed action.",
            "Real-world validation requires authorized representative event data, independently reviewed outcomes, actual report/response timestamps, operational definitions, privacy/security/legal review, and out-of-time and subgroup evaluation.",
        ],
        "cases": case_rows,
    }
    serialized = _json_ready(result)
    json_path = Path(output_json)
    csv_path = Path(output_csv)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(serialized, indent=2, allow_nan=False), encoding="utf-8")
    _write_case_csv(csv_path, case_rows, delay_curves)
    return serialized


def _write_case_csv(path: Path, cases: list[dict[str, Any]], delay_curves: list[list[dict[str, Any]]]) -> None:
    delay_fields = (
        "estimated_exposure_remaining_bdt",
        "estimated_exposure_already_cashed_out_bdt",
        "estimated_total_potentially_exposed_bdt",
        "downstream_wallets_identified",
        "maximum_downstream_hops_identified",
        "cashout_events_before_intervention",
    )
    fields = list(cases[0].keys()) if cases else ["scenario_id"]
    for curve in delay_curves:
        for row in curve:
            for field in delay_fields:
                name = f"delay_{row['delay_minutes']}m_{field}"
                if name not in fields:
                    fields.append(name)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for index, case in enumerate(cases):
            row = dict(case)
            for delay in delay_curves[index] if index < len(delay_curves) else []:
                for field in delay_fields:
                    row[f"delay_{delay['delay_minutes']}m_{field}"] = delay[field]
            writer.writerow(_json_ready(row))


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze synthetic financial exposure and response-delay scenarios.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON_PATH)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument(
        "--delays", default=",".join(str(value) for value in DEFAULT_DELAY_WINDOWS_MINUTES),
        help="Comma-separated response delay windows in minutes (default: 0,5,10,15,30,60).",
    )
    args = parser.parse_args()
    try:
        delays = tuple(int(value.strip()) for value in args.delays.split(",") if value.strip())
        result = run_impact_analysis(
            args.database, args.output_json, args.output_csv,
            delay_windows_minutes=delays,
        )
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "synthetic_data": result["synthetic_data"],
        "scenario_count": result["case_count"],
        "aggregate_metrics": result["aggregate_metrics"],
        "response_delay_metrics": result["response_delay_metrics"],
        "output_json": str(args.output_json.resolve()),
        "output_csv": str(args.output_csv.resolve()),
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
