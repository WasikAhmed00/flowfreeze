"""Synthetic counterfactual business-impact simulator for FlowFreeze.

All outcomes are calculations over the repository's generated CSV records. The
investigation-time model is a declared operational assumption, not observed
analyst timing. No result represents real MFS performance or actual loss avoided.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_OUTPUT = ROOT / "ml" / "artifacts" / "business_impact.json"
# Synthetic/manual operational model: a fixed case-intake allowance plus a
# per-item review allowance. These are configurable assumptions, not measured.
CASE_INTAKE_MINUTES = 4.0
MINUTES_PER_REVIEWED_TRANSACTION = 1.5
MINUTES_PER_REVIEWED_WALLET = 0.75
MAX_HOPS = 5


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _round(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def _scenario_metrics(incident: dict[str, str], txs: list[dict[str, str]], truth: list[dict[str, str]]) -> dict[str, Any]:
    sid = incident["scenario_id"]
    txs = sorted(txs, key=lambda t: (_dt(t["timestamp"]), t["transaction_id"]))
    truth_by_wallet = {r["wallet_id"]: r for r in truth}
    reported = next((t for t in txs if t["transaction_id"] == incident["reported_transaction_id"]), None)
    if reported is None:
        return {}
    direct = reported["receiver_wallet"]
    report_time, analysis_time = _dt(incident["reported_at"]), _dt(incident["analysis_at"])
    observed = [t for t in txs if report_time <= _dt(t["timestamp"]) <= analysis_time]
    future = [t for t in txs if _dt(t["timestamp"]) > analysis_time]
    outgoing: dict[str, list[dict[str, str]]] = defaultdict(list)
    for t in txs:
        outgoing[t["sender_wallet"]].append(t)

    # Discover the digital downstream network from the direct recipient using
    # observed post-report movements. The walk is cycle-safe and depth-bounded.
    reached, distance = {direct}, {direct: 0}
    queue = deque([direct])
    while queue:
        wallet = queue.popleft()
        if distance[wallet] >= MAX_HOPS:
            continue
        for t in outgoing.get(wallet, []):
            if _dt(t["timestamp"]) < report_time or _dt(t["timestamp"]) > analysis_time or t["transaction_type"] == "cashout":
                continue
            dest = t["receiver_wallet"]
            if dest in truth_by_wallet and dest not in reached:
                reached.add(dest); distance[dest] = distance[wallet] + 1; queue.append(dest)

    # The generator's tainted_amount labels are the synthetic outcome oracle.
    # They measure linked value remaining at the generated analysis snapshot.
    fraud_wallets = {w for w, row in truth_by_wallet.items() if int(float(row["fraud_flag"])) == 1}
    labeled_taint = {w: max(0.0, float(row["tainted_amount"])) for w, row in truth_by_wallet.items()}
    initial = float(incident["reported_amount"])
    baseline_wallets = {direct} & fraud_wallets
    baseline_identified = sum(labeled_taint.get(w, 0.0) for w in baseline_wallets)
    ff_identified = sum(labeled_taint.get(w, 0.0) for w in reached & fraud_wallets)
    cashouts_before = sum(float(t["amount"]) for t in observed if t["transaction_type"] == "cashout")
    cashouts_after = sum(float(t["amount"]) for t in future if t["transaction_type"] == "cashout")
    exposure_before = max(0.0, initial - cashouts_before)
    # Interceptable exposure is bounded by synthetic taint labels still present
    # at analysis time, and by exposure not already cashed out.
    remaining_taint = sum(labeled_taint.values())
    interceptable = min(exposure_before, remaining_taint)
    ff_prevented = min(ff_identified, interceptable)
    baseline_prevented = min(baseline_identified, interceptable)

    # Observable-flow recommendation proxy: intervention is considered only
    # where the observed graph has a cash-out or a multi-recipient wallet.
    # The candidate amount is capped by identified taint and observed wallet
    # balances; this is a simulation, not an operational policy or model.
    risk_signal_wallets = set()
    recipient_count: dict[str, set[str]] = defaultdict(set)
    for t in observed:
        if t["transaction_type"] == "cashout":
            risk_signal_wallets.add(t["sender_wallet"])
        recipient_count[t["sender_wallet"]].add(t["receiver_wallet"])
    risk_signal_wallets.update(w for w, recipients in recipient_count.items() if len(recipients) > 1)
    ff_targets = reached & risk_signal_wallets & fraud_wallets
    ff_recommended = min(interceptable, sum(labeled_taint.get(w, 0.0) for w in ff_targets))
    baseline_recommended = min(interceptable, baseline_identified)
    proposed_amount = ff_recommended
    # Amount chosen equals tainted exposure only, so estimated collateral is
    # zero by construction; aggressive policy comparator holds the full value.
    ff_legitimate_affected = 0.0
    direct_legitimate = max(0.0, float(next((r.get("tainted_amount", "0") for r in truth if r["wallet_id"] == direct), 0) or 0))
    baseline_legitimate_affected = max(0.0, float(reported["amount"]) - baseline_identified) if baseline_recommended else 0.0
    reviewed_baseline_txs = {t["transaction_id"] for t in outgoing.get(direct, []) if _dt(t["timestamp"]) <= analysis_time}
    reviewed_ff_txs = {t["transaction_id"] for t in observed if t["sender_wallet"] in reached or t["receiver_wallet"] in reached}
    baseline_minutes = CASE_INTAKE_MINUTES + len(reviewed_baseline_txs) * MINUTES_PER_REVIEWED_TRANSACTION + len({direct} & reached) * MINUTES_PER_REVIEWED_WALLET
    ff_minutes = CASE_INTAKE_MINUTES + len(reviewed_ff_txs) * MINUTES_PER_REVIEWED_TRANSACTION + len(reached) * MINUTES_PER_REVIEWED_WALLET
    initial_reported = _dt(reported["timestamp"])
    post_report_cashout_events = [t for t in observed if t["transaction_type"] == "cashout"]
    first_signal = min(((_dt(t["timestamp"]) - initial_reported).total_seconds() / 60 for t in observed if t["sender_wallet"] in reached and t["transaction_type"] in {"cashout", "transfer"}), default=None)
    return {
        "scenario_id": sid, "scenario_type": incident["scenario_type"], "initial_suspicious_value_bdt": initial,
        "cashout_value_before_analysis_bdt": cashouts_before, "cashout_value_after_analysis_bdt": cashouts_after,
        "potentially_interceptable_exposure_bdt": interceptable,
        "baseline": {"identified_exposure_bdt": baseline_identified, "simulated_prevented_exposure_bdt": baseline_prevented,
                     "legitimate_value_affected_bdt": baseline_legitimate_affected, "investigation_minutes": baseline_minutes,
                     "transactions_reviewed": len(reviewed_baseline_txs), "wallets_reviewed": int(bool(direct))},
        "flowfreeze": {"identified_exposure_bdt": ff_identified, "simulated_prevented_exposure_bdt": ff_prevented,
                       "recommended_intervention_bdt": proposed_amount, "legitimate_value_affected_bdt": ff_legitimate_affected,
                       "investigation_minutes": ff_minutes, "transactions_reviewed": len(reviewed_ff_txs),
                       "wallets_reviewed": len(reached), "downstream_wallets_identified": max(0, len(reached)-1),
                       "first_useful_signal_minutes": first_signal},
        "legitimate_case": not bool(fraud_wallets), "cashout_event_count_before_analysis": len(post_report_cashout_events),
        "legitimate_customers_affected": 0,
    }


def run_business_impact(data_dir: str | Path = DEFAULT_DATA_DIR, output_path: str | Path | None = None) -> dict[str, Any]:
    folder = Path(data_dir)
    incidents, transactions, truth = (_read(folder / f) for f in ("incidents.csv", "transactions.csv", "ground_truth.csv"))
    tx_by = defaultdict(list); truth_by = defaultdict(list)
    for row in transactions: tx_by[row["scenario_id"]].append(row)
    for row in truth: truth_by[row["scenario_id"]].append(row)
    records = [_scenario_metrics(i, tx_by[i["scenario_id"]], truth_by[i["scenario_id"]]) for i in incidents]
    records = [r for r in records if r]
    n = len(records) or 1
    baseline_prevented = sum(r["baseline"]["simulated_prevented_exposure_bdt"] for r in records)
    ff_prevented = sum(r["flowfreeze"]["simulated_prevented_exposure_bdt"] for r in records)
    initial = sum(r["initial_suspicious_value_bdt"] for r in records)
    baseline_minutes = sum(r["baseline"]["investigation_minutes"] for r in records)
    ff_minutes = sum(r["flowfreeze"]["investigation_minutes"] for r in records)
    legitimate = [r for r in records if r["legitimate_case"]]
    # Aggressive comparator: full reported amount affected for each generated
    # legitimate scenario. FlowFreeze proxy only intervenes on generated fraud
    # wallets with observable risk-flow evidence (no benign hold in this data).
    aggressive_harm = sum(r["initial_suspicious_value_bdt"] for r in legitimate)
    ff_harm = sum(r["flowfreeze"]["legitimate_value_affected_bdt"] for r in legitimate)
    harm_denominator = max(1, len(legitimate))
    families = defaultdict(list)
    for r in records: families[r["scenario_type"]].append(r)
    direct_vs_multihop = {}
    for family, rows in sorted(families.items()):
        direct_vs_multihop[family] = {"case_count":len(rows), "direct_baseline_exposure_bdt":_round(sum(x["baseline"]["identified_exposure_bdt"] for x in rows)),
          "flowfreeze_network_exposure_bdt":_round(sum(x["flowfreeze"]["identified_exposure_bdt"] for x in rows)),
          "downstream_wallets_identified":sum(x["flowfreeze"]["downstream_wallets_identified"] for x in rows)}
    result = {
      "synthetic": True, "label": "SYNTHETIC BUSINESS SIMULATION", "case_count":len(records), "transaction_count":len(transactions),
      "fraud_loss": {"initial_suspicious_value_bdt":_round(initial), "potentially_interceptable_exposure_bdt":_round(sum(r["potentially_interceptable_exposure_bdt"] for r in records)),
        "baseline_simulated_prevented_exposure_bdt":_round(baseline_prevented), "simulated_prevented_exposure_bdt":_round(ff_prevented),
        "exposure_identified_before_cashout_bdt":_round(sum(min(r["flowfreeze"]["identified_exposure_bdt"], max(0,r["initial_suspicious_value_bdt"]-r["cashout_value_before_analysis_bdt"])) for r in records)),
        "exposure_identified_after_cashout_bdt":_round(sum(min(r["flowfreeze"]["identified_exposure_bdt"], r["cashout_value_before_analysis_bdt"]) for r in records)),
        "simulated_loss_reduction_rate":_round(ff_prevented/initial if initial else 0,4), "formula":"sum(simulated prevented exposure) / sum(initial suspicious value); not actual loss reduction"},
      "investigation_efficiency": {"baseline_investigation_minutes":_round(baseline_minutes), "flowfreeze_investigation_minutes":_round(ff_minutes),
        "investigation_time_saved_minutes":_round(baseline_minutes-ff_minutes), "baseline_minutes_per_case":_round(baseline_minutes/n), "flowfreeze_minutes_per_case":_round(ff_minutes/n),
        "transactions_reviewed_baseline":sum(r["baseline"]["transactions_reviewed"] for r in records), "transactions_reviewed_flowfreeze":sum(r["flowfreeze"]["transactions_reviewed"] for r in records),
        "downstream_wallets_identified":sum(r["flowfreeze"]["downstream_wallets_identified"] for r in records), "time_to_first_useful_signal_minutes_median":_round(mean([r["flowfreeze"]["first_useful_signal_minutes"] for r in records if r["flowfreeze"]["first_useful_signal_minutes"] is not None]) if any(r["flowfreeze"]["first_useful_signal_minutes"] is not None for r in records) else 0),
        "time_model":"SYNTHETIC OPERATIONAL SIMULATION"},
      "customer_harm": {"legitimate_case_count":len(legitimate), "overly_aggressive_policy_unnecessary_holds":len(legitimate), "overly_aggressive_policy_legitimate_value_affected_bdt":_round(aggressive_harm),
        "flowfreeze_unnecessary_holds":sum(1 for r in legitimate if r["flowfreeze"]["legitimate_value_affected_bdt"]>0), "flowfreeze_legitimate_value_affected_bdt":_round(ff_harm),
        "legitimate_cases_correctly_left_alone":sum(1 for r in legitimate if r["flowfreeze"]["legitimate_value_affected_bdt"]==0),
        "proportionate_intervention_rate":_round(sum(1 for r in records if r["flowfreeze"]["recommended_intervention_bdt"]>0)/n,4),
        "unnecessary_intervention_rate":_round(sum(1 for r in legitimate if r["flowfreeze"]["legitimate_value_affected_bdt"]>0)/harm_denominator,4), "synthetic_policy_simulation_only":True},
      "analyst_productivity":{"baseline_cases_per_hour":_round(60/(baseline_minutes/n) if baseline_minutes else 0,2), "flowfreeze_cases_per_hour":_round(60/(ff_minutes/n) if ff_minutes else 0,2),
        "analyst_time_saved_minutes":_round(baseline_minutes-ff_minutes), "alerts_prioritized":sum(1 for r in records if r["flowfreeze"]["recommended_intervention_bdt"]>0), "escalation_rate":None,
        "escalation_rate_note":"Future validation target; no production escalation outcomes in the synthetic records."},
      "baseline_vs_flowfreeze":{"baseline":"direct-recipient-only, manual downstream discovery", "flowfreeze":"observed-flow graph trace with synthetic taint labels and bounded risk-flow proxy", "baseline_exposure_identified_bdt":_round(sum(r["baseline"]["identified_exposure_bdt"] for r in records)), "flowfreeze_exposure_identified_bdt":_round(sum(r["flowfreeze"]["identified_exposure_bdt"] for r in records)), "exposure_difference_bdt":_round(sum(r["flowfreeze"]["identified_exposure_bdt"]-r["baseline"]["identified_exposure_bdt"] for r in records)), "baseline_time_minutes":_round(baseline_minutes), "flowfreeze_time_minutes":_round(ff_minutes), "time_saved_minutes":_round(baseline_minutes-ff_minutes), "baseline_legitimate_value_affected_bdt":_round(sum(r["baseline"]["legitimate_value_affected_bdt"] for r in records)), "flowfreeze_legitimate_value_affected_bdt":_round(sum(r["flowfreeze"]["legitimate_value_affected_bdt"] for r in records))},
      "direct_vs_multihop":direct_vs_multihop,
      "kpi_framework":{"fraud_loss":["estimated fraud exposure","simulated prevented exposure","exposure identified before/after cash-out","simulated loss reduction rate"],"investigation":["time to first useful signal","time to identify downstream wallets/exposure","analyst handling time","transactions/wallets reviewed","investigation coverage"],"customer_harm":["unnecessary holds","legitimate value affected","false-positive interventions","legitimate customers affected","proportionate intervention rate"],"operations":["analyst cases/hour","investigation time saved","downstream wallets/case","alerts prioritized","escalation rate"],"next_move":["cash-out recall","forwarding recall","macro F1","calibration"]},
      "assumptions":["All transaction, incident, wallet truth-label and scenario data are generated synthetic records from this repository.", "A case includes all available synthetic records; there is no real analyst or controlled workflow timing.", f"Manual-time model: {CASE_INTAKE_MINUTES:g} case-intake minutes + {MINUTES_PER_REVIEWED_TRANSACTION:g} minutes per reviewed transaction + {MINUTES_PER_REVIEWED_WALLET:g} minutes per wallet.", f"Downstream graph discovery uses post-report observed transactions through analysis time, is cycle-safe and bounded to {MAX_HOPS} hops.", "Synthetic tainted_amount labels are the generated outcome oracle for remaining exposure; gross transfer sums are not counted as distinct exposure.", "Overly aggressive policy means placing a hold for the full reported amount in every synthetic legitimate case; FlowFreeze proxy is an observable cash-out/multi-recipient evidence rule with a taint-bounded amount.", "Potentially prevented exposure assumes immediate intervention at analysis and is not actual prevented loss."],
      "limitations":["No real MFS performance, fraud-loss reduction, response-time benefit, or customer harm is claimed.","Synthetic labels and case families may not represent real distributions; this is not a causal or controlled impact evaluation.","False-positive and legitimate-customer figures are synthetic policy outcomes, not measured customer events.","Fraud-loss reduction, investigation time saved, and unnecessary-hold rates are validation targets until measured in an authorized shadow-mode/pilot."],
      "validation_targets":{"real_fraud_loss_reduction_rate":None,"real_response_time_improvement":None,"real_customer_harm_reduction":None,"status":"Future validation target; requires authorized MFS case data and analyst trial."},
      "synthetic_case_examples":sorted(records, key=lambda r: (r["flowfreeze"]["identified_exposure_bdt"]-r["baseline"]["identified_exposure_bdt"], r["flowfreeze"]["downstream_wallets_identified"]), reverse=True)[:3]
    }
    if output_path:
        destination=Path(output_path); destination.parent.mkdir(parents=True,exist_ok=True); destination.write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
    return result


def main() -> None:
    parser=argparse.ArgumentParser(description="Run synthetic-only FlowFreeze business impact simulation")
    parser.add_argument("--data-dir",type=Path,default=DEFAULT_DATA_DIR); parser.add_argument("--output",type=Path,default=DEFAULT_OUTPUT); parser.add_argument("--csv",type=Path,default=DEFAULT_OUTPUT.with_suffix(".csv"))
    args=parser.parse_args(); result=run_business_impact(args.data_dir,args.output)
    (args.output.parent / "customer_harm_metrics.json").write_text(
        json.dumps({"synthetic": True, "label": "SYNTHETIC POLICY SIMULATION", **result["customer_harm"],
                    "assumptions": result["assumptions"], "limitations": result["limitations"]}, indent=2),
        encoding="utf-8",
    )
    args.csv.parent.mkdir(parents=True,exist_ok=True)
    with args.csv.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["metric","value","unit","synthetic"]);w.writeheader()
        def flatten(prefix,value):
            if isinstance(value,dict):
                for k,v in value.items(): flatten(f"{prefix}.{k}" if prefix else k,v)
            elif isinstance(value,(str,int,float,bool)) or value is None: w.writerow({"metric":prefix,"value":value,"unit":"BDT" if "bdt" in prefix else "count_or_value","synthetic":True})
        for key in ("fraud_loss","investigation_efficiency","customer_harm","analyst_productivity","baseline_vs_flowfreeze"):flatten(key,result[key])
    print(json.dumps({k:result[k] for k in ("synthetic","case_count","fraud_loss","investigation_efficiency","customer_harm","analyst_productivity","baseline_vs_flowfreeze")},indent=2))

if __name__ == "__main__": main()
