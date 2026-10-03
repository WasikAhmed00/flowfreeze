"""Stress tests for synthetic model metrics.

These analyses are deliberately diagnostic: they make it harder to mistake a
high same-family score for evidence of real-world performance.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, balanced_accuracy_score, f1_score
from data_generator.config import DEFAULT_DATA_DIR, DEFAULT_RANDOM_SEED
from ml.features import FEATURE_COLUMNS, build_feature_table
from ml.train import DEFAULT_ARTIFACT_DIR, _fraud_candidates


def _fit_predict(train: pd.DataFrame, test: pd.DataFrame, seed: int) -> np.ndarray:
    model = _fraud_candidates(seed)["logistic_regression"]
    model.fit(train[FEATURE_COLUMNS], train["fraud_flag"].astype(int))
    classes = list(model.classes_)
    return model.predict_proba(test[FEATURE_COLUMNS])[:, classes.index(1)]


def _metrics(y: pd.Series, probabilities: np.ndarray) -> dict[str, float]:
    threshold = 0.5
    return {
        "prevalence": float(y.mean()),
        "average_precision": float(average_precision_score(y, probabilities)),
        "balanced_accuracy": float(balanced_accuracy_score(y, probabilities >= threshold)),
        "f1": float(f1_score(y, probabilities >= threshold, zero_division=0)),
    }


def run_robustness(data_dir: str | Path = DEFAULT_DATA_DIR, artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR, seed: int = DEFAULT_RANDOM_SEED, bootstrap_reps: int = 200) -> dict[str, Any]:
    table = build_feature_table(data_dir)
    train = table[table["split"] == "train"].copy()
    test = table[table["split"] == "test"].copy()
    probabilities = _fit_predict(train, test, seed)
    result: dict[str, Any] = {"synthetic_only": True, "seed": seed, "test_rows": len(test), "test_cases": int(test["scenario_id"].nunique())}
    result["prevalence_baseline"] = {"positive_rate": float(test["fraud_flag"].mean()), "majority_accuracy": float(max(test["fraud_flag"].mean(), 1 - test["fraud_flag"].mean()))}
    result["trained_model"] = _metrics(test["fraud_flag"], probabilities)
    rule = ((test["observed_cashout_count"] > 0) | (test["observed_outgoing_count"] >= 2)).astype(int)
    result["behavior_rule_baseline"] = {"balanced_accuracy": float(balanced_accuracy_score(test["fraud_flag"], rule)), "f1": float(f1_score(test["fraud_flag"], rule, zero_division=0))}
    shuffled = train.copy()
    shuffled["fraud_flag"] = np.random.default_rng(seed).permutation(shuffled["fraud_flag"].to_numpy())
    shuffled_probabilities = _fit_predict(shuffled, test, seed)
    result["shuffled_label_check"] = _metrics(test["fraud_flag"], shuffled_probabilities)
    case_ids = test["scenario_id"].unique()
    rng = np.random.default_rng(seed)
    bootstrap_scores: list[float] = []
    grouped = test.assign(score=probabilities).groupby("scenario_id").agg(
        fraud_flag=("fraud_flag", "max"), score=("score", "mean")
    )
    for _ in range(max(1, bootstrap_reps)):
        sample = grouped.iloc[rng.integers(0, len(grouped), len(grouped))]
        bootstrap_scores.append(float(average_precision_score(sample["fraud_flag"], sample["score"])))
    result["scenario_cluster_bootstrap"] = {"repetitions": max(1, bootstrap_reps), "average_precision_mean": float(np.mean(bootstrap_scores)), "ci95": [float(np.quantile(bootstrap_scores, 0.025)), float(np.quantile(bootstrap_scores, 0.975))]}
    families = sorted(test["scenario_type"].unique())
    leave_out: dict[str, Any] = {}
    for family in families:
        train_without = pd.concat([train, table[(table["split"] == "validation") & (table["scenario_type"] != family)]], ignore_index=True)
        family_test = test[test["scenario_type"] == family]
        if family_test.empty or train_without["fraud_flag"].nunique() < 2:
            continue
        leave_out[family] = {"rows": len(family_test), **_metrics(family_test["fraud_flag"], _fit_predict(train_without, family_test, seed))}
    result["leave_one_family_out"] = leave_out
    result["interpretation"] = "Robustness checks are synthetic diagnostics. Cluster intervals and family holdouts are not production validation."
    output = Path(artifact_dir) / "robustness.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FlowFreeze synthetic model robustness checks.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED)
    parser.add_argument("--bootstrap-reps", type=int, default=200)
    args = parser.parse_args()
    print(json.dumps(run_robustness(args.data_dir, args.artifact_dir, args.seed, args.bootstrap_reps), indent=2))


if __name__ == "__main__":
    main()
