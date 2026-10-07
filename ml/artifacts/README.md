# Generated ML artifacts

`metrics.json` and `explanations.json` are reviewable synthetic evaluation outputs and are tracked. The reproducible trained pipelines (`fraud_model.joblib`, `next_move_model.joblib`) are intentionally ignored by Git; run `python -m ml.train --seed 42` locally to recreate them. The analysis API returns unavailable scores until both local models exist. Never load artifacts from an untrusted source.


`fairness_evaluation.json` / `.csv` and `false_positive_impact.json` / `.csv` are reproducible aggregate-only outputs from `python -m core.fairness_analysis`. They use only the repository's synthetic wallet-case labels and operational profile cohorts, hold the train/validation/test split discipline, and contain no wallet/scenario/transaction identifiers. Generate the synthetic dataset and train the local pipelines first. These outputs are exploratory synthetic diagnostics—not evidence of demographic fairness, actual customer impact, or Upay/MFS production performance. Read `docs/FAIRNESS_AND_HARM.md` before interpreting or using them.
