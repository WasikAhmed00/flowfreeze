"""Synthetic subgroup fairness and false-positive impact evaluation.

No wallet/scenario identifiers are emitted. Segment boundaries are fixed for
account age and learned from training profiles only for activity and amount.
Threshold selection uses the existing validation-selected model threshold; the
held-out test split is reporting-only.
"""
from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

import numpy as np
import pandas as pd

from data_generator.config import DEFAULT_DATA_DIR
from ml.calibration import apply_multiclass_calibrators
from ml.features import FEATURE_COLUMNS, build_feature_table
from ml.train import DEFAULT_ARTIFACT_DIR

DEFAULT_OUTPUT_DIR = DEFAULT_ARTIFACT_DIR
THRESHOLD_GRID = (0.50, 0.60, 0.70, 0.80, 0.90)
MIN_GROUP_SIZE = 20
MIN_CLASS_SUPPORT = 5
SEGMENT_COLUMNS = (
    "customer_type",
    "account_age_bucket",
    "transaction_activity_bucket",
    "amount_profile_bucket",
)
GAP_METRICS = ("false_positive_rate", "false_negative_rate", "true_positive_rate", "precision")
CASE_INTAKE_MINUTES = 4.0
MINUTES_PER_REVIEWED_TRANSACTION = 1.5
MINUTES_PER_REVIEWED_WALLET = 0.75


def _number(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if not np.isfinite(numeric):
        return None
    return round(numeric, digits)


def _binary_metrics(
    y_true: Iterable[int],
    scores: Iterable[float],
    threshold: float,
    *,
    min_group_size: int = MIN_GROUP_SIZE,
    min_class_support: int = MIN_CLASS_SUPPORT,
) -> dict[str, Any]:
    y = np.asarray(list(y_true), dtype=int)
    score = np.asarray(list(scores), dtype=float)
    if len(y) != len(score) or not len(y):
        raise ValueError("Binary metrics require equally sized, non-empty label and score arrays.")
    if np.any(~np.isfinite(score)) or np.any((score < 0) | (score > 1)):
        raise ValueError("Risk scores must be finite values between zero and one.")
    pred = (score >= threshold).astype(int)
    tp = int(np.sum((y == 1) & (pred == 1)))
    fp = int(np.sum((y == 0) & (pred == 1)))
    tn = int(np.sum((y == 0) & (pred == 0)))
    fn = int(np.sum((y == 1) & (pred == 0)))
    n_pos, n_neg, n_pred_pos = tp + fn, tn + fp, tp + fp
    precision = tp / n_pred_pos if n_pred_pos else None
    recall = tp / n_pos if n_pos else None
    specificity = tn / n_neg if n_neg else None
    fpr = fp / n_neg if n_neg else None
    fnr = fn / n_pos if n_pos else None
    f1 = (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and precision + recall else (0.0 if precision is not None and recall == 0 else None)
    support_ok = len(y) >= min_group_size
    pos_ok, neg_ok = n_pos >= min_class_support, n_neg >= min_class_support
    try:
        from sklearn.metrics import average_precision_score
        pr_auc = float(average_precision_score(y, score)) if support_ok and pos_ok and neg_ok else None
    except ValueError:
        pr_auc = None
    metric_reliability = {
        "false_positive_rate": support_ok and neg_ok,
        "specificity": support_ok and neg_ok,
        "false_negative_rate": support_ok and pos_ok,
        "true_positive_rate": support_ok and pos_ok,
        "recall": support_ok and pos_ok,
        "precision": support_ok and pos_ok and n_pred_pos >= min_class_support,
        "f1": support_ok and pos_ok and neg_ok,
        "pr_auc_average_precision": support_ok and pos_ok and neg_ok,
        "mean_risk_score": support_ok,
        "high_risk_alert_rate": support_ok,
    }
    return {
        "sample_count": int(len(y)),
        "fraud_count": int(n_pos),
        "legitimate_count": int(n_neg),
        "fraud_prevalence": _number(n_pos / len(y)),
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": _number(precision),
        "recall": _number(recall),
        "true_positive_rate": _number(recall),
        "specificity": _number(specificity),
        "true_negative_rate": _number(specificity),
        "false_positive_rate": _number(fpr),
        "false_negative_rate": _number(fnr),
        "f1": _number(f1),
        "pr_auc_average_precision": _number(pr_auc),
        "mean_risk_score": _number(float(score.mean())),
        "high_risk_alert_rate": _number(float(pred.mean())),
        "reliability": {
            "minimum_group_size": int(min_group_size),
            "minimum_class_support": int(min_class_support),
            "positive_support_sufficient": bool(pos_ok),
            "negative_support_sufficient": bool(neg_ok),
            "status": "meets_exploratory_minimums" if support_ok and pos_ok and neg_ok else "unreliable_small_or_one_class_sample",
            "metric_reliable": metric_reliability,
            "caveat": "Minimum support flags are screening rules, not confidence intervals, significance tests, or evidence of fairness.",
        },
    }


def _quantile_cutpoints(values: pd.Series) -> tuple[float, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if not len(clean):
        raise ValueError("Cannot create activity/amount cohorts without training-profile values.")
    low, high = np.quantile(clean, [1 / 3, 2 / 3], method="linear")
    return float(low), float(high)


def _tertile(value: Any, low: float, high: float) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if not np.isfinite(numeric):
        return "UNKNOWN"
    if numeric <= low:
        return "LOW"
    if numeric <= high:
        return "MEDIUM"
    return "HIGH"


def _with_segments(table: pd.DataFrame, data_dir: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    profiles = pd.read_csv(Path(data_dir) / "wallets.csv", keep_default_na=False)
    required = {"scenario_id", "wallet_id", "customer_type", "account_age", "transaction_frequency", "average_transaction_amount"}
    missing = required - set(profiles.columns)
    if missing:
        raise ValueError("Synthetic wallet profiles are missing required cohort fields: " + ", ".join(sorted(missing)))
    cohorts = table.merge(
        profiles[list(required)], on=["scenario_id", "wallet_id"], how="left", validate="one_to_one",
    )
    if cohorts["customer_type"].isna().any() or (cohorts["customer_type"].astype(str).str.strip() == "").any():
        raise ValueError("Some labeled wallets have no existing synthetic customer_type category.")
    train = cohorts[cohorts["split"] == "train"]
    activity_low, activity_high = _quantile_cutpoints(train["transaction_frequency"])
    amount_low, amount_high = _quantile_cutpoints(train["average_transaction_amount"])
    account_age = pd.to_numeric(cohorts["account_age"], errors="coerce")
    cohorts["customer_type"] = cohorts["customer_type"].astype(str)
    cohorts["account_age_bucket"] = np.select(
        [account_age <= 90, account_age <= 365], ["NEW", "ESTABLISHED"], default="LONG_TENURE",
    )
    cohorts["transaction_activity_bucket"] = [
        _tertile(value, activity_low, activity_high) for value in cohorts["transaction_frequency"]
    ]
    cohorts["amount_profile_bucket"] = [
        f"{_tertile(value, amount_low, amount_high)}_VALUE" for value in cohorts["average_transaction_amount"]
    ]
    boundaries = {
        "account_age_bucket_days": {"NEW": "<=90", "ESTABLISHED": "91-365", "LONG_TENURE": ">365"},
        "transaction_activity_bucket": {
            "source_field": "transaction_frequency (synthetic historical transactions/day)",
            "method": "one-third/two-thirds quantiles computed from train-split wallet profiles only",
            "train_cutpoints": {"low_upper_inclusive": _number(activity_low, 4), "medium_upper_inclusive": _number(activity_high, 4)},
        },
        "amount_profile_bucket": {
            "source_field": "average_transaction_amount (synthetic BDT profile)",
            "method": "one-third/two-thirds quantiles computed from train-split wallet profiles only",
            "train_cutpoints_bdt": {"low_upper_inclusive": _number(amount_low, 2), "medium_upper_inclusive": _number(amount_high, 2)},
        },
        "customer_type": {"source_field": "existing synthetic wallets.csv customer_type categories", "categories": sorted(cohorts["customer_type"].unique().tolist())},
    }
    return cohorts, boundaries


def _read_context(data_dir: str | Path, labeled: pd.DataFrame) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any], dict[tuple[str, str], int], dict[tuple[str, str], str]]:
    folder = Path(data_dir)
    incidents = pd.read_csv(folder / "incidents.csv", keep_default_na=False)
    cutoffs = {
        str(row.scenario_id): pd.to_datetime(row.analysis_at, utc=True).to_pydatetime()
        for row in incidents.itertuples(index=False)
    }
    transactions = pd.read_csv(folder / "transactions.csv", keep_default_na=False)
    transactions["_time"] = pd.to_datetime(transactions["timestamp"], format="mixed", utc=True, errors="raise")
    tx_by_scenario = {
        str(sid): group.to_dict("records")
        for sid, group in transactions.groupby("scenario_id", sort=False)
    }
    truth = {
        (str(row.scenario_id), str(row.wallet_id)): int(row.fraud_flag)
        for row in labeled[["scenario_id", "wallet_id", "fraud_flag"]].itertuples(index=False)
    }
    profiles = pd.read_csv(folder / "wallets.csv", keep_default_na=False)
    wallet_types = {
        (str(row.scenario_id), str(row.wallet_id)): str(row.customer_type)
        for row in profiles[["scenario_id", "wallet_id", "customer_type"]].itertuples(index=False)
    }
    return tx_by_scenario, cutoffs, truth, wallet_types


def _keys_for_rows(rows: pd.DataFrame) -> set[tuple[str, str]]:
    return {(str(scenario), str(wallet)) for scenario, wallet in rows[["scenario_id", "wallet_id"]].itertuples(index=False, name=None)}


def _affected_legitimate_transactions(
    keys: set[tuple[str, str]],
    tx_by_scenario: dict[str, list[dict[str, Any]]],
    cutoffs: dict[str, Any],
    truth: dict[tuple[str, str], int],
    wallet_types: dict[tuple[str, str], str],
) -> dict[tuple[str, str], Decimal]:
    affected: dict[tuple[str, str], Decimal] = {}
    if not keys:
        return affected
    scenarios = {scenario for scenario, _ in keys}
    for scenario in scenarios:
        cutoff = cutoffs.get(scenario)
        if cutoff is None:
            continue
        for event in tx_by_scenario.get(scenario, []):
            if event["_time"].to_pydatetime() > cutoff:
                continue
            sender_key = (scenario, str(event["sender_wallet"]))
            receiver_key = (scenario, str(event["receiver_wallet"]))
            participants = (sender_key, receiver_key)
            affected_participants = [key for key in participants if key in keys]
            if not affected_participants:
                continue
            # Count only generated events between profiles labeled legitimate,
            # or cash-outs to the generator's explicit non-customer destination.
            non_destination = [key for key in participants if wallet_types.get(key) != "cash_destination"]
            if not non_destination or any(truth.get(key) != 0 for key in non_destination):
                continue
            amount = Decimal(str(event["amount"])).quantize(Decimal("0.01"))
            affected[(scenario, str(event["transaction_id"]))] = amount
    return affected


def _workload(selected: pd.DataFrame, tx_by_scenario: dict[str, list[dict[str, Any]]], cutoffs: dict[str, Any]) -> dict[str, Any]:
    keys = _keys_for_rows(selected)
    scenarios = {scenario for scenario, _ in keys}
    reviewed_transactions: set[tuple[str, str]] = set()
    for scenario in scenarios:
        cutoff = cutoffs.get(scenario)
        if cutoff is None:
            continue
        wallets = {wallet for sid, wallet in keys if sid == scenario}
        for event in tx_by_scenario.get(scenario, []):
            if event["_time"].to_pydatetime() <= cutoff and (
                str(event["sender_wallet"]) in wallets or str(event["receiver_wallet"]) in wallets
            ):
                reviewed_transactions.add((scenario, str(event["transaction_id"])))
    minutes = (
        len(scenarios) * CASE_INTAKE_MINUTES
        + len(reviewed_transactions) * MINUTES_PER_REVIEWED_TRANSACTION
        + len(keys) * MINUTES_PER_REVIEWED_WALLET
    )
    return {
        "review_case_count": len(scenarios),
        "review_wallet_count": len(keys),
        "unique_transactions_in_review_scope": len(reviewed_transactions),
        "estimated_analyst_workload_minutes": round(minutes, 2),
        "workload_formula": f"{CASE_INTAKE_MINUTES:g} intake min/case + {MINUTES_PER_REVIEWED_TRANSACTION:g} min/unique associated transaction + {MINUTES_PER_REVIEWED_WALLET:g} min/wallet; synthetic assumption, not measured analyst time",
    }


def _false_positive_impact(
    population: pd.DataFrame,
    candidate_mask: Iterable[bool],
    tx_by_scenario: dict[str, list[dict[str, Any]]],
    cutoffs: dict[str, Any],
    truth: dict[tuple[str, str], int],
    wallet_types: dict[tuple[str, str], str],
) -> dict[str, Any]:
    mask = np.asarray(list(candidate_mask), dtype=bool)
    if len(mask) != len(population):
        raise ValueError("Candidate mask length must match the population.")
    fp_rows = population.iloc[np.flatnonzero(mask & (population["fraud_flag"].to_numpy(dtype=int) == 0))]
    legitimate_population = int((population["fraud_flag"].to_numpy(dtype=int) == 0).sum())
    total_affected = _affected_legitimate_transactions(_keys_for_rows(fp_rows), tx_by_scenario, cutoffs, truth, wallet_types)
    values = [float(value) for value in total_affected.values()]
    segment_rows: list[dict[str, Any]] = []
    cases_per_segment: dict[str, dict[str, int]] = {}
    value_per_segment: dict[str, dict[str, float]] = {}
    for dimension in SEGMENT_COLUMNS:
        case_counts: dict[str, int] = {}
        value_counts: dict[str, float] = {}
        for category in sorted(population[dimension].astype(str).unique()):
            category_rows = fp_rows[fp_rows[dimension].astype(str) == category]
            category_keys = _keys_for_rows(category_rows)
            category_events = _affected_legitimate_transactions(category_keys, tx_by_scenario, cutoffs, truth, wallet_types)
            case_count = int(category_rows["scenario_id"].nunique())
            value = float(sum(category_events.values(), Decimal("0.00")))
            case_counts[category] = case_count
            value_counts[category] = round(value, 2)
            segment_rows.append({
                "segment_dimension": dimension,
                "segment": category,
                "legitimate_wallet_population": int((population[dimension].astype(str).eq(category) & population["fraud_flag"].eq(0)).sum()),
                "false_positive_wallets": int(len(category_rows)),
                "affected_case_count": case_count,
                "affected_legitimate_transaction_count": len(category_events),
                "simulated_legitimate_value_affected_bdt": round(value, 2),
            })
        cases_per_segment[dimension] = case_counts
        value_per_segment[dimension] = value_counts
    fp_count = int(len(fp_rows))
    return {
        "false_positive_count": fp_count,
        "false_positive_rate": _number(fp_count / legitimate_population if legitimate_population else None),
        "legitimate_wallet_population": legitimate_population,
        "affected_legitimate_transaction_count": len(total_affected),
        "legitimate_value_affected_bdt": round(float(sum(total_affected.values(), Decimal("0.00"))), 2),
        "average_legitimate_value_affected_bdt": round(mean(values), 2) if values else None,
        "median_legitimate_value_affected_bdt": round(median(values), 2) if values else None,
        "customer_segments_affected": [
            {"segment_dimension": row["segment_dimension"], "segment": row["segment"], "false_positive_wallets": row["false_positive_wallets"]}
            for row in segment_rows if row["false_positive_wallets"] > 0
        ],
        "cases_per_segment": cases_per_segment,
        "value_per_segment": value_per_segment,
        "segment_impact": segment_rows,
        "value_definition": "Deduplicated gross amount of generated, pre-analysis transactions between ground-truth legitimate profiles (or to an explicit cash_destination) associated with a false-positive wallet-case. This is simulated legitimate transaction value exposed to possible interruption under the stated policy, not actual customer harm, loss, or a hold.",
    }


def _with_scores(
    cohorts: pd.DataFrame,
    model_artifacts: str | Path,
) -> tuple[pd.DataFrame, float, float, str]:
    import joblib

    artifact_dir = Path(model_artifacts)
    fraud_path = artifact_dir / "fraud_model.joblib"
    move_path = artifact_dir / "next_move_model.joblib"
    if not fraud_path.exists() or not move_path.exists():
        raise FileNotFoundError(
            f"Synthetic model files are missing in {artifact_dir}; run `python -m ml.train --seed 42` first."
        )
    fraud = joblib.load(fraud_path)
    movement = joblib.load(move_path)
    threshold = float(fraud["decision_threshold"])
    validation = cohorts[cohorts["split"] == "validation"]
    if validation.empty:
        raise ValueError("A validation split is required to honor threshold-selection discipline.")
    classes = list(movement["pipeline"].classes_)
    if "cashout" not in classes:
        raise ValueError("Next-move model lacks the required cashout class for urgency evaluation.")
    validation_probabilities = apply_multiclass_calibrators(
        movement["pipeline"].predict_proba(validation[FEATURE_COLUMNS]), classes, movement["calibrators"],
    )
    urgency_cutoff = float(np.quantile(validation_probabilities[:, classes.index("cashout")], 0.75, method="linear"))
    scored = cohorts.copy()
    scored["risk_score"] = np.nan
    scored["next_move_cashout_probability"] = np.nan
    for split in ("validation", "test"):
        subset = scored[scored["split"] == split]
        if subset.empty:
            raise ValueError(f"A {split} split is required for the requested evaluation.")
        x = subset[FEATURE_COLUMNS]
        fraud_classes = list(fraud["pipeline"].classes_)
        risks = fraud["pipeline"].predict_proba(x)[:, fraud_classes.index(1)]
        move_probabilities = apply_multiclass_calibrators(
            movement["pipeline"].predict_proba(x), classes, movement["calibrators"],
        )
        scored.loc[subset.index, "risk_score"] = risks
        scored.loc[subset.index, "next_move_cashout_probability"] = move_probabilities[:, classes.index("cashout")]
    return scored, threshold, urgency_cutoff, str(fraud.get("model_name", "unknown"))


def _attach_metrics(frame: pd.DataFrame, threshold: float, min_group_size: int, min_class_support: int) -> dict[str, Any]:
    return _binary_metrics(
        frame["fraud_flag"].astype(int), frame["risk_score"], threshold,
        min_group_size=min_group_size, min_class_support=min_class_support,
    )


def _gap_comparisons(segment_metrics: dict[str, list[dict[str, Any]]], overall: dict[str, Any]) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    lower_is_better = {"false_positive_rate", "false_negative_rate"}
    for dimension, rows in segment_metrics.items():
        metric_results: dict[str, Any] = {}
        for metric in GAP_METRICS:
            eligible = [row for row in rows if row["metrics"]["reliability"]["metric_reliable"].get(metric) and row["metrics"].get(metric) is not None]
            values = [(row["segment"], float(row["metrics"][metric])) for row in eligible]
            overall_value = overall.get(metric)
            if not values:
                metric_results[metric] = {"status": "no_segments_meet_minimum_support", "overall_value": overall_value, "eligible_segment_count": 0}
                continue
            best = min(values, key=lambda item: item[1]) if metric in lower_is_better else max(values, key=lambda item: item[1])
            worst = max(values, key=lambda item: item[1]) if metric in lower_is_better else min(values, key=lambda item: item[1])
            metric_results[metric] = {
                "status": "exploratory_comparison_only",
                "direction_for_reference": "lower_is_better" if metric in lower_is_better else "higher_is_better",
                "overall_value": overall_value,
                "eligible_segment_count": len(values),
                "segment_minus_overall": [
                    {"segment": name, "value": value, "signed_gap": _number(value - overall_value) if overall_value is not None else None,
                     "absolute_gap": _number(abs(value - overall_value)) if overall_value is not None else None}
                    for name, value in values
                ],
                "best_observed_segment": {"segment": best[0], "value": _number(best[1]), "gap_vs_overall": _number(best[1] - overall_value) if overall_value is not None else None},
                "worst_observed_segment": {"segment": worst[0], "value": _number(worst[1]), "gap_vs_overall": _number(worst[1] - overall_value) if overall_value is not None else None},
                "best_to_worst_absolute_gap": _number(max(value for _, value in values) - min(value for _, value in values)),
            }
        comparisons[dimension] = metric_results
    return comparisons


def _policy_comparison(
    test: pd.DataFrame,
    threshold: float,
    urgency_cutoff: float,
    tx_by_scenario: dict[str, list[dict[str, Any]]],
    cutoffs: dict[str, Any],
    truth: dict[tuple[str, str], int],
    wallet_types: dict[tuple[str, str], str],
) -> list[dict[str, Any]]:
    high_risk = test["risk_score"].to_numpy(dtype=float) >= threshold
    exposure_proxy = np.minimum(
        pd.to_numeric(test["reported_amount_bdt"], errors="coerce").fillna(0).to_numpy(dtype=float),
        pd.to_numeric(test["observed_outgoing_amount_bdt"], errors="coerce").fillna(0).to_numpy(dtype=float),
    )
    ratio = pd.to_numeric(test["amount_to_prior_average_ratio"], errors="coerce").fillna(0).to_numpy(dtype=float)
    prior_relationships = pd.to_numeric(test["prior_relationship_count"], errors="coerce").fillna(0).to_numpy(dtype=float)
    outgoing = pd.to_numeric(test["observed_outgoing_count"], errors="coerce").fillna(0).to_numpy(dtype=float)
    counterparties = pd.to_numeric(test["distinct_counterparties"], errors="coerce").fillna(0).to_numpy(dtype=float)
    cashouts = pd.to_numeric(test["observed_cashout_count"], errors="coerce").fillna(0).to_numpy(dtype=float)
    urgency = test["next_move_cashout_probability"].to_numpy(dtype=float) >= urgency_cutoff
    graph_signal = ((outgoing > 0) & (counterparties >= 2)) | (cashouts > 0)
    explanation_signals = np.column_stack([
        (ratio >= 2.0) & (prior_relationships > 0),
        outgoing >= 1,
        graph_signal,
        urgency,
        cashouts > 0,
    ]).sum(axis=1)
    evidence_qualified = high_risk & (explanation_signals >= 2) & (exposure_proxy > 0) & graph_signal & urgency
    strategies = [
        ("aggressive", "Aggressive intervention", high_risk,
         "Counterfactual intervention on every risk score at or above the validation-selected threshold; no additional evidence gate."),
        ("evidence_based", "Evidence-based with analyst review", evidence_qualified,
         "Risk threshold plus at least two listed behavior/explanation signals, positive estimated-exposure proxy, validation-derived cash-out urgency cutoff, and graph/cash-out evidence; candidate remains subject to human analyst review."),
    ]
    results = []
    for key, name, mask, definition in strategies:
        selected = test.iloc[np.flatnonzero(mask)]
        selected_mask = np.zeros(len(test), dtype=bool)
        selected_mask[np.flatnonzero(mask)] = True
        harm = _false_positive_impact(test, selected_mask, tx_by_scenario, cutoffs, truth, wallet_types)
        fraud_total = int(test["fraud_flag"].sum())
        selected_fraud = int(selected["fraud_flag"].sum())
        missed_fraud = fraud_total - selected_fraud
        results.append({
            "strategy": key,
            "label": name,
            "definition": definition,
            "risk_threshold": _number(threshold),
            "risk_threshold_source": "fraud_model.decision_threshold selected on validation split by ml.train.py; not chosen from test results",
            "candidate_wallet_case_recommendations": int(len(selected)),
            "high_risk_fraud_recall": _number(selected_fraud / fraud_total if fraud_total else None),
            "true_positive_rate": _number(selected_fraud / fraud_total if fraud_total else None),
            "false_negative_count": missed_fraud,
            "missed_fraud_rate": _number(missed_fraud / fraud_total if fraud_total else None),
            "precision": _number(selected_fraud / len(selected) if len(selected) else None),
            "false_positive_count": harm["false_positive_count"],
            "false_positive_rate": harm["false_positive_rate"],
            "simulated_legitimate_value_affected_bdt": harm["legitimate_value_affected_bdt"],
            "affected_legitimate_transaction_count": harm["affected_legitimate_transaction_count"],
            "explanation_strength_distribution": {
                str(signal_count): int(np.sum(selected_mask & (explanation_signals == signal_count)))
                for signal_count in range(6)
            },
            "customer_impact_exposure_is_actual": False,
            "analyst_workload": _workload(selected, tx_by_scenario, cutoffs),
            "human_review_required_before_any_action": key == "evidence_based",
            "automatic_execution": False,
            "synthetic_only": True,
        })
    return results


def run_fairness_evaluation(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    model_artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    min_group_size: int = MIN_GROUP_SIZE,
    min_class_support: int = MIN_CLASS_SUPPORT,
    thresholds: Iterable[float] = THRESHOLD_GRID,
) -> dict[str, Any]:
    """Generate aggregate-only JSON/CSV fairness and false-positive reports."""
    if min_group_size < 1 or min_class_support < 1:
        raise ValueError("Minimum sample support must be positive.")
    configured_thresholds = tuple(sorted({float(value) for value in thresholds}))
    if not configured_thresholds or any(not np.isfinite(value) or value < 0 or value > 1 for value in configured_thresholds):
        raise ValueError("Configure one or more finite risk thresholds in the inclusive range [0, 1].")
    folder = Path(data_dir)
    base_table = build_feature_table(folder)
    cohorts, boundaries = _with_segments(base_table, folder)
    scored, threshold, urgency_cutoff, model_name = _with_scores(cohorts, model_artifact_dir)
    validation = scored[scored["split"] == "validation"].copy()
    test = scored[scored["split"] == "test"].copy()
    overall = _attach_metrics(test, threshold, min_group_size, min_class_support)
    segment_metrics: dict[str, list[dict[str, Any]]] = {}
    csv_rows: list[dict[str, Any]] = []
    for dimension in SEGMENT_COLUMNS:
        rows = []
        for category, subset in test.groupby(dimension, sort=True, dropna=False):
            metrics = _attach_metrics(subset, threshold, min_group_size, min_class_support)
            gaps = {
                metric: {
                    "signed_gap_vs_overall": _number(metrics[metric] - overall[metric]) if metrics[metric] is not None and overall[metric] is not None else None,
                    "absolute_gap_vs_overall": _number(abs(metrics[metric] - overall[metric])) if metrics[metric] is not None and overall[metric] is not None else None,
                    "reliable": bool(metrics["reliability"]["metric_reliable"].get(metric, False)),
                }
                for metric in GAP_METRICS
            }
            row = {"segment": str(category), "metrics": metrics, "gaps_vs_overall": gaps}
            rows.append(row)
            csv_rows.append({
                "segment_dimension": dimension, "segment": str(category), "threshold": threshold,
                **{key: metrics.get(key) for key in (
                    "sample_count", "fraud_count", "legitimate_count", "fraud_prevalence",
                    "precision", "recall", "true_positive_rate", "specificity", "false_positive_rate",
                    "false_negative_rate", "f1", "pr_auc_average_precision", "mean_risk_score", "high_risk_alert_rate",
                )},
                "metric_reliability_json": json.dumps(metrics["reliability"]["metric_reliable"], sort_keys=True),
                "reliability_status": metrics["reliability"]["status"],
                "fpr_gap_vs_overall": gaps["false_positive_rate"]["signed_gap_vs_overall"],
                "fnr_gap_vs_overall": gaps["false_negative_rate"]["signed_gap_vs_overall"],
                "tpr_gap_vs_overall": gaps["true_positive_rate"]["signed_gap_vs_overall"],
                "precision_gap_vs_overall": gaps["precision"]["signed_gap_vs_overall"],
            })
        segment_metrics[dimension] = rows
    comparisons = _gap_comparisons(segment_metrics, overall)

    tx_by_scenario, cutoffs, truth, wallet_types = _read_context(folder, cohorts)
    operating_mask = test["risk_score"].to_numpy(dtype=float) >= threshold
    overall_harm = _false_positive_impact(test, operating_mask, tx_by_scenario, cutoffs, truth, wallet_types)
    false_positive_report = {
        "synthetic": True,
        "label": "SYNTHETIC FALSE-POSITIVE IMPACT EVALUATION",
        "evaluation_split": "test",
        "threshold": _number(threshold),
        "threshold_source": "Existing ml.train.py decision threshold selected on validation split; test split was not used to select or tune it.",
        "overall": overall_harm,
        "unit_of_analysis": "wallet-case prediction; false-positive rate is false-positive legitimate wallet-cases divided by all legitimate wallet-cases in the evaluation split.",
        "limitations": [
            "Ground-truth labels, segments and transaction values are generated synthetic records, not real customers or real service events.",
            "Affected value is deduplicated generated legitimate transaction volume associated with a false-positive wallet-case; it is not a loss, actual hold, or verified customer harm.",
            "Group support flags are exploratory minimums, not significance tests or confidence intervals.",
        ],
    }
    threshold_rows = []
    threshold_points = sorted(set(configured_thresholds) | {threshold})
    for candidate_threshold in threshold_points:
        metrics = _attach_metrics(validation, candidate_threshold, min_group_size, min_class_support)
        mask = validation["risk_score"].to_numpy(dtype=float) >= candidate_threshold
        impact = _false_positive_impact(validation, mask, tx_by_scenario, cutoffs, truth, wallet_types)
        workload = _workload(validation.iloc[np.flatnonzero(mask)], tx_by_scenario, cutoffs)
        threshold_rows.append({
            "threshold": candidate_threshold,
            "threshold_analysis_split": "validation",
            "selected_model_threshold": _number(threshold),
            "matches_model_selected_threshold": bool(abs(candidate_threshold - threshold) < 1e-12),
            "metrics": metrics,
            "false_positive_count": impact["false_positive_count"],
            "legitimate_value_affected_bdt": impact["legitimate_value_affected_bdt"],
            "analyst_workload": workload,
        })
    validation_metrics = _attach_metrics(validation, threshold, min_group_size, min_class_support)
    policy_results = _policy_comparison(test, threshold, urgency_cutoff, tx_by_scenario, cutoffs, truth, wallet_types)
    metadata_path = folder / "generation_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {"synthetic": True, "seed": None}
    synthetic_warning = (
        "These segments are evaluation cohorts, not protected-attribute proxies, and should not be interpreted as evidence of fairness across protected demographic groups. "
        "Synthetic fairness evaluation does not establish fairness on real MFS customers."
    )
    fairness_report = {
        "synthetic": True,
        "label": "SYNTHETIC FAIRNESS EVALUATION — NOT PRODUCTION VALIDATION",
        "data_seed": metadata.get("seed"),
        "model_name": model_name,
        "evaluation_split": "test",
        "test_threshold": _number(threshold),
        "test_threshold_source": "Existing model threshold selected on validation by ml.train.py; no threshold optimization is performed on test.",
        "threshold_analysis": {
            "split": "validation",
            "thresholds": threshold_points,
            "configured_thresholds": list(configured_thresholds),
            "selected_model_threshold": _number(threshold),
            "selected_threshold_criterion": "The existing ml.train.py validation F1 selection; this report does not select a new operating threshold.",
            "validation_metrics_are_selection_data": True,
            "points": threshold_rows,
            "warning": "The validation sweep shares data with model/threshold selection and is descriptive only, not held-out performance. Use the test results only at the preselected model threshold and select any future operating point on validation followed by a real-world governed pilot.",
        },
        "dataset": {
            "synthetic_only": True,
            "seed": metadata.get("seed"),
            "scenario_family_count": metadata.get("scenario_family_count"),
            "scenario_cases_by_split": metadata.get("split_case_counts"),
            "wallet_case_rows_by_split": {str(k): int(v) for k, v in cohorts.groupby("split").size().to_dict().items()},
        },
        "cohort_methodology": {
            "segment_dimensions": list(SEGMENT_COLUMNS),
            "boundaries": boundaries,
            "variables_used": ["customer_type", "account_age", "transaction_frequency", "average_transaction_amount"],
            "why_selected": {
                "customer_type": "Existing synthetic operational customer categories in wallets.csv.",
                "account_age_bucket": "Existing synthetic account age, grouped into new, established and longer-tenure operational cohorts.",
                "transaction_activity_bucket": "Existing generated historical transaction-frequency profile; train-only tertiles avoid hand-tuned performance cohorts.",
                "amount_profile_bucket": "Existing generated average-transaction-amount profile; train-only tertiles avoid hand-tuned performance cohorts.",
            },
            "excluded_variables": ["race", "religion", "political_affiliation", "sexual_orientation", "other protected or sensitive personal attributes", "wallet_id", "scenario_id"],
            "unit_of_analysis": "one synthetic wallet-case prediction at the generator's analysis_at snapshot",
            "warning": synthetic_warning,
        },
        "overall_test_metrics": overall,
        "test_metrics_by_segment": segment_metrics,
        "gap_comparisons": comparisons,
        "false_positive_impact": {
            "false_positive_count": overall_harm["false_positive_count"],
            "false_positive_rate": overall_harm["false_positive_rate"],
            "legitimate_value_affected_bdt": overall_harm["legitimate_value_affected_bdt"],
            "affected_legitimate_transaction_count": overall_harm["affected_legitimate_transaction_count"],
            "cases_per_segment": overall_harm["cases_per_segment"],
            "value_per_segment": overall_harm["value_per_segment"],
        },
        "intervention_policy_comparison": {
            "evaluation_split": "test",
            "threshold_source": "validation-selected model threshold; test set was not used for selection",
            "estimated_exposure_proxy": "min(reported_amount_bdt, observed_outgoing_amount_bdt) at analysis_at, used only as a synthetic policy input; not ground-truth taint or recoverable funds",
            "next_move_urgency_cutoff": {"value": _number(urgency_cutoff), "source": "75th percentile of calibrated cash-out probabilities on validation split only"},
            "evidence_rule": {
                "minimum_signals": 2,
                "listed_signals": [
                    "amount ratio >=2 with a prior relationship",
                    "observed outgoing count >=1",
                    "graph evidence: (observed outgoing count >0 and distinct counterparties >=2) or an observed cash-out",
                    "calibrated cash-out probability >= the validation urgency cutoff",
                    "observed cash-out count >0",
                ],
                "requires_positive_estimated_exposure": True,
                "requires_graph_evidence": True,
                "requires_validation_urgency_cutoff": True,
                "human_review_required": True,
                "automatic_execution": False,
                "warning": "Signals are overlapping heuristics, not statistically independent evidence or validated operational rules.",
            },
            "results": policy_results,
            "warning": "Both strategies are decision counterfactuals only. Evidence-based candidates still need a human analyst; no action was executed and no real customer impact was measured.",
        },
        "sample_size_policy": {
            "minimum_segment_population": min_group_size,
            "minimum_positive_and_negative_class_support": min_class_support,
            "description": "Metrics failing a relevant minimum are marked unreliable and omitted from reliable-segment gap comparisons; these minimums do not prove statistical significance.",
        },
        "limitations": [
            "Synthetic fairness evaluation does not establish fairness on real MFS customers.",
            "These segments are evaluation cohorts, not protected-attribute proxies, and should not be interpreted as evidence of fairness across protected demographic groups.",
            "The generated cases repeat eleven scenario families across splits; this test does not measure new-family or real-world generalization.",
            "No confidence intervals, hypothesis tests, causal conclusions, subgroup representativeness claim, or production validation is provided.",
            "False-positive value is synthetic legitimate transaction volume potentially exposed to interruption, not actual financial/customer harm.",
        ],
    }
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "fairness_evaluation.json").write_text(json.dumps(fairness_report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (out_dir / "false_positive_impact.json").write_text(json.dumps(false_positive_report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    pd.DataFrame(csv_rows).to_csv(out_dir / "fairness_evaluation.csv", index=False)
    impact_csv = [{
        "segment_dimension": "overall", "segment": "all_test_wallet_cases",
        "legitimate_wallet_population": overall_harm["legitimate_wallet_population"],
        "false_positive_wallets": overall_harm["false_positive_count"],
        "affected_case_count": int(test.iloc[np.flatnonzero(operating_mask)]["scenario_id"].nunique()),
        "affected_legitimate_transaction_count": overall_harm["affected_legitimate_transaction_count"],
        "simulated_legitimate_value_affected_bdt": overall_harm["legitimate_value_affected_bdt"],
        "average_legitimate_value_affected_bdt": overall_harm["average_legitimate_value_affected_bdt"],
        "median_legitimate_value_affected_bdt": overall_harm["median_legitimate_value_affected_bdt"],
        "false_positive_rate": overall_harm["false_positive_rate"],
    }]
    for row in overall_harm["segment_impact"]:
        dimension = row["segment_dimension"]
        category = row["segment"]
        impact_csv.append({
            **row,
            "average_legitimate_value_affected_bdt": None,
            "median_legitimate_value_affected_bdt": None,
            "false_positive_rate": _number(
                row["false_positive_wallets"] / row["legitimate_wallet_population"]
                if row["legitimate_wallet_population"] else None
            ),
        })
    pd.DataFrame(impact_csv).to_csv(out_dir / "false_positive_impact.csv", index=False)
    return {"fairness_evaluation": fairness_report, "false_positive_impact": false_positive_report}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate synthetic FlowFreeze subgroup errors and false-positive impact.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--model-artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-group-size", type=int, default=MIN_GROUP_SIZE)
    parser.add_argument("--min-class-support", type=int, default=MIN_CLASS_SUPPORT)
    parser.add_argument("--thresholds", type=_parse_thresholds, default=THRESHOLD_GRID, help="Comma-separated validation diagnostic thresholds in [0,1], e.g. 0.5,0.6,0.7,0.8,0.9")
    args = parser.parse_args()
    results = run_fairness_evaluation(
        args.data_dir, args.model_artifact_dir, args.output_dir,
        min_group_size=args.min_group_size, min_class_support=args.min_class_support,
        thresholds=args.thresholds,
    )
    fairness = results["fairness_evaluation"]
    impact = results["false_positive_impact"]["overall"]
    print(json.dumps({
        "artifacts": str(args.output_dir.resolve()),
        "evaluation_split": fairness["evaluation_split"],
        "threshold": fairness["test_threshold"],
        "false_positive_count": impact["false_positive_count"],
        "synthetic_only": True,
        "warning": "Synthetic evaluation is not real MFS fairness or customer-harm validation.",
    }, indent=2))


def _parse_thresholds(value: str) -> tuple[float, ...]:
    try:
        values = tuple(sorted({float(part.strip()) for part in value.split(",") if part.strip()}))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Thresholds must be comma-separated numbers.") from exc
    if not values or any(not np.isfinite(item) or item < 0 or item > 1 for item in values):
        raise argparse.ArgumentTypeError("Specify one or more thresholds in the inclusive range [0, 1].")
    return values


if __name__ == "__main__":
    main()
