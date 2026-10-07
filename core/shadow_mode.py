"""Synthetic shadow-mode simulation; records recommendations, never actions."""
from __future__ import annotations
import argparse, csv, hashlib, json
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from sklearn.metrics import average_precision_score, precision_score, recall_score
from core.business_impact import DEFAULT_DATA_DIR, _dt, _read

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "ml" / "artifacts" / "shadow_mode.json"
EVENT_CSV = ROOT / "ml" / "artifacts" / "shadow_mode_events.csv"
TARGETS_PATH = ROOT / "core" / "pilot_targets.json"
TARGET_STATUS = "TARGET TO BE AGREED DURING PILOT"


def _pseudonym(value: str) -> str:
    return "case_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def run_shadow_mode(data_dir: str | Path = DEFAULT_DATA_DIR, output_path: str | Path | None = None, targets_path: str | Path = TARGETS_PATH) -> dict:
    folder = Path(data_dir)
    incidents = _read(folder / "incidents.csv")
    transactions = _read(folder / "transactions.csv")
    truth = _read(folder / "ground_truth.csv")
    target_config=json.loads(Path(targets_path).read_text(encoding="utf-8"))
    if target_config.get("status") != TARGET_STATUS or not isinstance(target_config.get("targets"),dict):
        raise ValueError(f"Pilot targets must retain status {TARGET_STATUS!r} and a targets mapping.")
    for name,item in target_config["targets"].items():
        if not isinstance(item,dict) or "target" not in item:
            raise ValueError(f"Pilot target {name!r} must define a target field (null until agreed).")
        value=item["target"]
        if value is not None and (not isinstance(value,(int,float)) or value < 0):
            raise ValueError(f"Pilot target {name!r} must be a non-negative number or null.")
    tx_by: dict[str, list[dict]] = defaultdict(list); truth_by: dict[str, list[dict]] = defaultdict(list)
    for row in transactions: tx_by[row["scenario_id"]].append(row)
    for row in truth: truth_by[row["scenario_id"]].append(row)
    events = []
    labels=[]; scores=[]; predicted=[]; baseline_predicted=[]
    total_trace_minutes=0.0; total_useful_minutes=[]; total_review_minutes=0.0; total_baseline_review_minutes=0.0; workload_items=0
    flowfreeze_exposure=0.0; estimated_prevented=0.0; legitimate_affected=0.0; legit_cases=0; false_positive_count=0; false_negative_count=0
    for incident in incidents:
        sid=incident["scenario_id"]; all_txs=sorted(tx_by[sid],key=lambda t:(_dt(t["timestamp"]),t["transaction_id"]))
        tx_by_id={t["transaction_id"]:t for t in all_txs}; reported=tx_by_id.get(incident["reported_transaction_id"])
        if not reported: continue
        report_at,as_of=_dt(incident["reported_at"]),_dt(incident["analysis_at"])
        observed=[t for t in all_txs if report_at <= _dt(t["timestamp"]) <= as_of]
        truth_rows=truth_by[sid]; truth_wallet={t["wallet_id"]:t for t in truth_rows}
        fraud_wallets={w for w,r in truth_wallet.items() if int(float(r["fraud_flag"]))==1}
        positive=bool(fraud_wallets)
        direct=reported["receiver_wallet"]
        outgoing:dict[str,list[dict]]=defaultdict(list)
        for t in observed: outgoing[t["sender_wallet"]].append(t)
        # Graph trace in shadow only: bounded, cycle-safe, and evidence-only.
        depth={direct:0}; q=deque([direct]); cashout_wallets=set(); multi_recipient=set()
        for wallet, rows in outgoing.items():
            if len({r["receiver_wallet"] for r in rows})>1: multi_recipient.add(wallet)
            if any(r["transaction_type"]=="cashout" for r in rows): cashout_wallets.add(wallet)
        while q:
            wallet=q.popleft()
            if depth[wallet]>=5: continue
            for t in outgoing.get(wallet,[]):
                if t["transaction_type"]=="cashout": continue
                dest=t["receiver_wallet"]
                if dest in truth_wallet and dest not in depth:
                    depth[dest]=depth[wallet]+1;q.append(dest)
        reached=set(depth)
        taint=sum(max(0.0,float(truth_wallet[w]["tainted_amount"])) for w in reached & fraud_wallets)
        baseline_taint=max(0.0,float(truth_wallet[direct]["tainted_amount"])) if direct in fraud_wallets else 0.0
        initial=float(incident["reported_amount"])
        observed_cashout=sum(float(t["amount"]) for t in observed if t["transaction_type"]=="cashout")
        remaining=max(0.0,initial-observed_cashout)
        exposure=min(taint,remaining)
        baseline_exposure=min(baseline_taint,remaining)
        # Current-process comparator: direct-recipient-only investigation.
        direct_score=min(.99,.15 + .25*bool(outgoing.get(direct)) + .25*bool(direct in cashout_wallets) + .10*(len(outgoing.get(direct,[]))>=2))
        # FlowFreeze shadow score is a transparent signal heuristic—not a trained
        # risk model. It combines direct and downstream flow evidence only.
        cashout_signal=bool(cashout_wallets & reached)
        branch_signal=bool(multi_recipient & reached)
        downstream_signal=len(reached)>1
        score=min(.99,.10+.22*bool(outgoing.get(direct))+.28*cashout_signal+.24*branch_signal+.15*downstream_signal)
        rec=score>=.55
        base_rec=direct_score>=.55
        labels.append(int(positive));scores.append(score);predicted.append(int(rec));baseline_predicted.append(int(base_rec))
        false_positive_count += int(rec and not positive);false_negative_count += int((not rec) and positive)
        useful=min(((_dt(t["timestamp"])-_dt(reported["timestamp"])).total_seconds()/60 for t in observed if t["sender_wallet"] in reached and t["transaction_type"] in {"transfer","cashout"}),default=None)
        if useful is not None: total_useful_minutes.append(useful)
        trace_min=max(0.0,(as_of-report_at).total_seconds()/60);total_trace_minutes+=trace_min
        # Identical disclosed synthetic timing model as business-impact module.
        reviewed={t["transaction_id"] for t in observed if t["sender_wallet"] in reached or t["receiver_wallet"] in reached}
        review_minutes=4.0+len(reviewed)*1.5+len(reached)*.75
        total_review_minutes+=review_minutes;workload_items+=len(reviewed)+len(reached)
        baseline_reviewed={t["transaction_id"] for t in outgoing.get(direct,[])}
        total_baseline_review_minutes+=4.0+len(baseline_reviewed)*1.5+(1.0 if direct else 0.0)*.75
        flowfreeze_exposure+=exposure
        # Never label this as loss avoided: a shadow recommendation cannot act.
        if rec: estimated_prevented+=exposure
        if not positive:
            legit_cases+=1
            if rec: legitimate_affected+=min(initial,taint)
        actual_decision=None; actual_outcome=None
        events.append({
            "case_id":_pseudonym(sid),"model_version":"flowfreeze-shadow-heuristic-v1",
            "risk_score":round(score,6),"predicted_next_move":"cashout" if cashout_signal else ("forward" if downstream_signal else "no_movement"),
            "trace_depth":max(depth.values(),default=0),"estimated_exposure_bdt":round(exposure,2),"baseline_estimated_exposure_bdt":round(baseline_exposure,2),
            "recommendation":"prioritize_for_analyst_review" if rec else "monitor_no_intervention_recommended",
            "actual_operator_decision":actual_decision,"actual_outcome":actual_outcome,
            "decision_timestamp":None,"flowfreeze_decision_timestamp":incident["analysis_at"],
            "analyst_review_time_minutes":None,"recommendation_agreement":None,
            "false_positive":bool(rec and not positive),"false_negative":bool((not rec) and positive),
            "estimated_exposure_difference_bdt":round(exposure-baseline_exposure,2),"synthetic":True,
            "automatic_execution":False,"financial_actions_executed":0,
            "evidence_summary":{"downstream_wallets":max(0,len(reached)-1),"observed_cashout_signal":cashout_signal,"multi_recipient_signal":branch_signal},
        })
    n=len(events) or 1
    precision=float(precision_score(labels,predicted,zero_division=0)) if events else 0.0
    recall=float(recall_score(labels,predicted,zero_division=0)) if events else 0.0
    pr_auc=float(average_precision_score(labels,scores)) if events and len(set(labels))>1 else None
    agreement=None;override=None;confidence=None;usefulness=None
    result={"synthetic":True,"label":"Synthetic shadow-mode simulation","pilot_label":"SIMULATED — NOT PRODUCTION DATA","automatic_execution":False,"financial_actions_executed":0,
      "cases_evaluated":len(events),"events":events,
      "current_process":{"description":"Synthetic direct-recipient-only observable-flow heuristic comparator; no actual operator records exist.","recommendations":sum(baseline_predicted),"synthetic_workload_minutes":round(total_baseline_review_minutes,2)},
      "flowfreeze_shadow":{"description":"Record-only observable-flow evidence heuristic; not a trained-model pilot and cannot execute actions.","recommendations":sum(predicted),"precision":round(precision,4),"recall":round(recall,4),"pr_auc_average_precision":round(pr_auc,4) if pr_auc is not None else None,"true_positives":sum(1 for y,p in zip(labels,predicted) if y and p),"actual_positive_cases":sum(labels),"false_positives":false_positive_count,"false_negatives":false_negative_count,"estimated_exposure_identified_bdt":round(flowfreeze_exposure,2),"simulated_prevented_exposure_bdt":round(estimated_prevented,2)},
      "investigation":{"time_to_useful_signal_median_minutes":round(sorted(total_useful_minutes)[len(total_useful_minutes)//2],2) if total_useful_minutes else None,"time_to_trace_median_minutes":round(total_trace_minutes/n,2),"synthetic_analyst_workload_minutes":round(total_review_minutes,2),"current_process_synthetic_workload_minutes":round(total_baseline_review_minutes,2),"estimated_time_saved_minutes":round(total_baseline_review_minutes-total_review_minutes,2),"reviewed_items":workload_items,"timing_model":"Synthetic event time and disclosed manual workload formula; not measured analyst timing."},
      "business":{"unnecessary_intervention_rate":round(sum(1 for e in events if e["false_positive"])/max(1,legit_cases),4),"legitimate_value_affected_bdt":round(legitimate_affected,2),"estimated_exposure_identified_bdt":round(flowfreeze_exposure,2),"simulated_prevented_exposure_bdt":round(estimated_prevented,2)},
      "human":{"analyst_agreement_rate":agreement,"recommendation_override_rate":override,"analyst_confidence":confidence,"recommendation_usefulness":usefulness,"status":"Unavailable in synthetic records; collect through analyst feedback during an authorized pilot."},
      "feedback_summary":{"feedback_records":0,"analyst_agreement_rate":None,"override_rate":None,"note":"Live analyst feedback is stored separately in the append-only feedback audit table."},
      "business_success_targets":target_config,
      "assumptions":["The current-process comparator and shadow output are deterministic synthetic heuristics, not real operational decisions or production model outputs.","Generated fraud_flag and tainted_amount labels are used only as synthetic reference outcomes.","Analyst agreement, override, confidence and usefulness are null because no analyst trial occurred.","Actual operator decisions, confirmed outcomes and real timestamps are intentionally null.","Recommendations are stored for evaluation only; no financial, account, transaction, customer-contact or provider action is called."],
      "limitations":["This is not a real pilot, shadow deployment, production measurement, or causal impact estimate.","Synthetic results cannot establish MFS precision, recall, customer harm, response-time improvement, or business value.","A partner must approve data governance, event mapping, thresholds, success criteria and stop criteria before any real-case phase."],
      "event_schema":["case_id","model_version","risk_score","predicted_next_move","trace_depth","estimated_exposure_bdt","baseline_estimated_exposure_bdt","recommendation","actual_operator_decision","actual_outcome","decision_timestamp","flowfreeze_decision_timestamp","analyst_review_time_minutes","recommendation_agreement","false_positive","false_negative","estimated_exposure_difference_bdt"]}
    if output_path:
        target=Path(output_path);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
        with target.with_name("shadow_mode_events.csv").open("w",newline="",encoding="utf-8") as f:
            fields=list(events[0]) if events else ["case_id","synthetic"]
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(events)
    return result


def main():
    parser=argparse.ArgumentParser(description="Run the synthetic-only, non-actuating shadow-mode simulation")
    parser.add_argument("--data-dir",type=Path,default=DEFAULT_DATA_DIR);parser.add_argument("--output",type=Path,default=OUTPUT);parser.add_argument("--targets",type=Path,default=TARGETS_PATH)
    args=parser.parse_args();r=run_shadow_mode(args.data_dir,args.output,args.targets)
    print(json.dumps({k:r[k] for k in ("synthetic","label","cases_evaluated","current_process","flowfreeze_shadow","investigation","business","human","automatic_execution","financial_actions_executed")},indent=2))

if __name__=="__main__":main()
