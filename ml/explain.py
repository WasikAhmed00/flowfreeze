"""Compute global permutation explanations for saved synthetic models.

These describe model reliance under the synthetic held-out distribution; they
are not causal explanations for an individual wallet or fraud determinations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sklearn.inspection import permutation_importance

from data_generator.config import DEFAULT_DATA_DIR
from ml.features import FEATURE_COLUMNS, build_feature_table
from ml.train import DEFAULT_ARTIFACT_DIR


def _top_permutation_features(model: Any, x: Any, y: Any, *, scoring: str, seed: int, top_n: int) -> list[dict[str, float | str]]:
    result = permutation_importance(
        model, x, y, scoring=scoring, n_repeats=3, random_state=seed, n_jobs=1,
    )
    order = result.importances_mean.argsort()[::-1][:top_n]
    return [
        {
            "feature": str(FEATURE_COLUMNS[index]),
            "mean_score_decrease": float(result.importances_mean[index]),
            "std_score_decrease": float(result.importances_std[index]),
        }
        for index in order
    ]


def explain_models(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    *,
    rows: int = 1000,
    top_n: int = 12,
    seed: int = 42,
) -> dict[str, Any]:
    import joblib

    table = build_feature_table(data_dir)
    test = table[table["split"] == "test"].head(rows)
    if test.empty:
        raise ValueError("No held-out test cases are available for explanations.")
    x = test[FEATURE_COLUMNS]
    fraud = joblib.load(Path(artifact_dir) / "fraud_model.joblib")
    movement = joblib.load(Path(artifact_dir) / "next_move_model.joblib")
    result = {
        "synthetic_only": True,
        "test_wallet_rows_sampled": int(len(test)),
        "fraud_model": {
            "model_name": fraud["model_name"],
            "method": "permutation importance using average precision",
            "top_features": _top_permutation_features(
                fraud["pipeline"], x, test["fraud_flag"].astype(int),
                scoring="average_precision", seed=seed, top_n=top_n,
            ),
        },
        "next_move_model": {
            "model_name": "class-balanced logistic regression",
            "method": "permutation importance using macro F1",
            "top_features": _top_permutation_features(
                movement["pipeline"], x, test["expected_next_action"].astype(str),
                scoring="f1_macro", seed=seed, top_n=top_n,
            ),
        },
        "warning": "Global permutation importance is distribution-dependent and is not causal or a per-wallet explanation.",
    }
    path = Path(artifact_dir) / "explanations.json"
    path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Explain saved FlowFreeze models with held-out permutation importance.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--top", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(explain_models(args.data_dir, args.artifact_dir, rows=args.rows, top_n=args.top, seed=args.seed), indent=2))


if __name__ == "__main__":
    main()
