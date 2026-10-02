# Generated ML artifacts

`metrics.json` and `explanations.json` are reviewable synthetic evaluation outputs and are tracked. The reproducible trained pipelines (`fraud_model.joblib`, `next_move_model.joblib`) are intentionally ignored by Git; run `python -m ml.train --seed 42` locally to recreate them. The analysis API returns unavailable scores until both local models exist. Never load artifacts from an untrusted source.
