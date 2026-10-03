# FlowFreeze Synthetic Model Card

## Intended use

The models are hackathon prototype components for exploring wallet-level fraud-linked-flow classification and likely next movement within five minutes. Their purpose is to exercise the data, feature, evaluation, and analyst-review workflow with generated records. They are not suitable for production account decisions, customer treatment, transaction blocking, or claims about upay BD performance.

## Data and labels

The seeded generator creates 1100 incident cases from eleven scenario families, with wallet-level labels in `ground_truth.csv`. Each case is assigned wholly to train, validation, or test. Rows from a case never cross splits. Inputs are built from the incident, wallet profiles, and transaction events visible by `analysis_at`; future events and ground-truth columns are excluded. Features intentionally omit scenario and wallet identifiers and absolute timestamps. See `ml/features.py` and `docs/DATA_DICTIONARY.md`.

## Models and selection

- Fraud: logistic regression and random forest candidates; validation average precision (PR-AUC) selects the model. A decision threshold is selected on validation F1.
- Next movement: class-balanced multinomial logistic regression. Validation-fitted one-vs-rest Platt scaling adjusts class scores, then blends them 50/50 with raw model probabilities before renormalizing; this preserves signal for the rare cash-out class while retaining probability correction. The test split is not used to fit the calibrators.
- Reproducibility: `python -m ml.train --seed 42`. The exact seed, split sizes, label counts, selected model, feature list, and held-out metrics are recorded in `ml/artifacts/metrics.json`.
- Explanations: `python -m ml.explain` computes global permutation importance on held-out synthetic records; this is not a causal or individual-wallet explanation.

## Evaluation

`python -m ml.evaluate` reports held-out fraud precision, recall, F1, average precision, balanced accuracy, and confusion matrix; next-move macro metrics, log loss, multiclass Brier score, and confusion matrix are reported too. The held-out split has 165 incident cases under the default data. Run `python -m ml.robustness` for prevalence, rule, shuffled-label, clustered-bootstrap, and leave-one-family-out diagnostics. Refer to generated JSON for measured values; no numbers here are assumed stable across generator or code changes.

## Limitations

The default generator includes eleven families, including legitimate relay, payroll split, and slow-mule cases. Case-level holdout is still synthetic and families overlap behaviorally; leave-one-family-out robustness diagnostics are reported separately. This is a case-level holdout, not an unseen-family, temporal, provider-shift, or real-customer evaluation. Features and labels are produced by the same synthetic scenario logic, and very high scores can reflect that shared design. The test is small and generated class proportions are artificial. Validation calibration does not establish calibration on real transactions. Robustness diagnostics include prevalence and behavior-rule baselines, shuffled-label checks, scenario-cluster bootstrap intervals, and leave-one-family-out results. These do not replace fairness, subgroup, adversarial, temporal, or operational monitoring evaluation.

## Human oversight and safeguards

Scores are labeled synthetic in the API and UI. The intervention policy is an independent, configurable layer and does not issue provider commands. A human analyst must review evidence and approve or modify any simulated proposal. Missing models or scores should produce monitoring/review behavior, not an inferred low risk. The demo must use generated identifiers and data only.

## End-to-end policy experiment

`python -m core.baseline --split test` compares direct-recipient-only and traced-network policy proposals on the same held-out scenarios. It uses remaining generator taint labels only for counterfactual outcome scoring; it assumes an instantaneous intervention at `analysis_at`. It is not measured loss prevention and it does not validate model quality beyond the separately reported held-out classifier metrics. See `docs/END_TO_END_EVALUATION.md` for the recorded results and detailed assumptions.
