# Responsible AI, Subgroup Errors, and Synthetic Customer-Impact Review

**Status:** exploratory synthetic evaluation; not a fairness certification, production result, or estimate of harm to real customers.

**Dashboard label:** “Synthetic evaluation — not production fairness validation.”

> These segments are evaluation cohorts, not protected-attribute proxies, and should not be interpreted as evidence of fairness across protected demographic groups.
>
> Synthetic fairness evaluation does not establish fairness on real MFS customers.

## 1. Evaluation objective and scope

This review adds an aggregate-only fairness and false-positive impact workflow to FlowFreeze. It measures whether model errors vary across existing synthetic operational cohorts and quantifies generated legitimate transaction value that a hypothetical intervention might expose.

The report does **not** test fairness across protected demographic groups. `customer_type`, account age, activity, and amount profile are cohorts already present in the synthetic generator, not protected attributes or validated proxies. No real Upay/MFS production integration, customer records, interventions, holds, appeals, or analyst timings were involved.

## 2. Dataset, split, and segmentation

- Source: repository synthetic generator, seed `42`, freshly generated for the run; 1,100 scenario cases from 11 scenario families (770 train, 165 validation, 165 test).
- Model: existing leakage-aware FlowFreeze fraud pipeline; `random_forest` selected on validation data. The operating threshold (`0.739618`) is the existing validation-F1 selection in the trained artifact.
- Unit: one synthetic non-cash-destination wallet in one generated scenario at its `analysis_at` snapshot. Test includes 1,155 wallet-case rows: 204 fraud-labeled and 951 legitimate-labeled.
- The fraud model's existing 20 decision-time behavioral features are unchanged. Cohorts are joined **after** scoring for evaluation only; they are not new model features.
- Value amounts are generated BDT transaction amounts. Wallet, scenario, transaction, case, and customer identifiers are not emitted in the aggregate reports or returned by the metrics API.

### Cohort definitions and rationale

| Cohort dimension | Existing synthetic source | Deterministic definition / rationale |
|---|---|---|
| Customer type | `wallets.csv.customer_type` | Existing generator categories; no new customer categories are invented. |
| Account age | `wallets.csv.account_age` | `NEW` <=90 days; `ESTABLISHED` 91–365 days; `LONG_TENURE` >365 days. Fixed operational age bands. |
| Transaction activity | `wallets.csv.transaction_frequency` | `LOW` / `MEDIUM` / `HIGH` one-third and two-thirds quantiles fitted on **train-split profiles only**, then applied unchanged to validation and test. |
| Amount profile | `wallets.csv.average_transaction_amount` | `LOW_VALUE` / `MEDIUM_VALUE` / `HIGH_VALUE` one-third and two-thirds quantiles fitted on **train-split profiles only**, then applied unchanged to validation and test. |

No race, religion, political affiliation, sexual orientation, or other sensitive personal attributes are used or required. Train-only tertiles avoid hand-tuning cutoffs after seeing test results. Empty and one-class groups remain visible but unsupported class-dependent metrics are flagged.

## 3. Metrics and threshold methodology

At the existing validation-selected threshold, the evaluator calculates sample count, fraud prevalence, precision, recall/true-positive rate (TPR), specificity/true-negative rate (TNR), false-positive rate (FPR), false-negative rate (FNR), F1, average-precision PR-AUC where supported, mean risk score, high-risk alert rate, and confusion counts for each cohort and overall. It also records signed/absolute differences from overall and the best/worst observed cohort plus best-to-worst range for FPR, FNR, TPR, and precision.

Exploratory reporting requires at least 20 rows and, for class-dependent metrics, at least five examples of each relevant class; PR-AUC requires at least five positive and five negative examples. A failed support rule suppresses unreliable metrics in gap comparisons but does not discard the cohort. **These thresholds are screening rules, not confidence intervals, significance tests, or proof of fairness.**

The diagnostic threshold list is configurable with `--thresholds` (for example `0.50,0.60,0.70,0.80,0.90`). The evaluator always adds the model's existing selected operating threshold if it is not already in the list. The fixed model threshold was selected on the validation split for F1. The complete sweep shares model/threshold selection data and is marked **validation/selection data**; it is descriptive, not held-out performance. No threshold is tuned on test. Any future operating point requires validation followed by a governed, independently assessed real-world pilot.

## 4. Seed-42 held-out synthetic test results

At the preselected threshold **0.739618**, the held-out test confusion counts are **TP=191, FP=5, TN=946, FN=13**. Precision is **97.45%**, TPR **93.63%**, FPR **0.53%** (5/951 legitimate wallet-cases), FNR **6.37%** (13/204 fraud wallet-cases), and average-precision PR-AUC **0.9873**.

These strong-looking synthetic scores primarily show consistency with this generator's repeated scenario families and labels; they are not estimates of real fraud performance.

### Cohort errors at the fixed test threshold

| Cohort dimension | Group | n | Fraud prevalence | TPR | FPR | FNR | Precision | Support note |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Customer type | Agent | 30 | 0.00% | — | 0.00% | — | — | No positive cases; class-dependent metrics suppressed. |
| Customer type | Individual | 885 | 21.69% | 93.75% | 0.58% | 6.25% | 97.83% | Exploratory minimums met. |
| Customer type | Merchant | 240 | 5.00% | 91.67% | 0.44% | 8.33% | 91.67% | Exploratory minimums met; 12 positive cases. |
| Account age | NEW | 41 | 29.27% | 100.00% | 0.00% | 0.00% | 100.00% | Exploratory minimums met; 12 positive cases. |
| Account age | ESTABLISHED | 148 | 18.24% | 88.89% | 0.00% | 11.11% | 100.00% | Exploratory minimums met; 27 positive cases. |
| Account age | LONG_TENURE | 966 | 17.08% | 93.94% | 0.62% | 6.06% | 96.88% | Exploratory minimums met. |
| Activity | LOW | 496 | 0.00% | — | 0.00% | — | — | No positive cases; class-dependent metrics suppressed. |
| Activity | MEDIUM | 279 | 26.52% | 94.59% | 1.95% | 5.41% | 94.59% | Exploratory minimums met. |
| Activity | HIGH | 380 | 34.21% | 93.08% | 0.40% | 6.92% | 99.18% | Exploratory minimums met. |
| Amount profile | LOW_VALUE | 391 | 3.07% | 83.33% | 0.00% | 16.67% | 100.00% | Exploratory minimums met; 12 positive cases. |
| Amount profile | MEDIUM_VALUE | 370 | 19.46% | 90.28% | 0.67% | 9.72% | 97.01% | Exploratory minimums met. |
| Amount profile | HIGH_VALUE | 394 | 30.46% | 96.67% | 1.09% | 3.33% | 97.48% | Exploratory minimums met. |

### Best/worst observed cohort gaps

These are descriptive best-to-worst absolute ranges among groups meeting the relevant support rule, not demographic-fairness rankings.

| Dimension | FPR: best → worst (gap) | FNR: best → worst (gap) | TPR: best → worst (gap) | Precision: best → worst (gap) |
|---|---|---|---|---|
| Customer type | Agent 0.00% → Individual 0.58% (0.58 pp) | Individual 6.25% → Merchant 8.33% (2.08 pp) | Individual 93.75% → Merchant 91.67% (2.08 pp) | Individual 97.83% → Merchant 91.67% (6.16 pp) |
| Account age | Established/New 0.00% → Long-tenure 0.62% (0.62 pp) | New 0.00% → Established 11.11% (11.11 pp) | New 100.00% → Established 88.89% (11.11 pp) | Established 100.00% → Long-tenure 96.88% (3.13 pp) |
| Activity | Low 0.00% → Medium 1.95% (1.95 pp) | Medium 5.41% → High 6.92% (1.52 pp) | Medium 94.59% → High 93.08% (1.52 pp) | High 99.18% → Medium 94.59% (4.59 pp) |
| Amount profile | LOW_VALUE 0.00% → HIGH_VALUE 1.09% (1.09 pp) | HIGH_VALUE 3.33% → LOW_VALUE 16.67% (13.33 pp) | HIGH_VALUE 96.67% → LOW_VALUE 83.33% (13.33 pp) | LOW_VALUE 100.00% → MEDIUM_VALUE 97.01% (2.99 pp) |

Agent and low-activity groups have no positive examples in this test sample, so TPR, FNR, precision, and related PR-AUC are unavailable and deliberately omitted. The larger low-amount-profile FNR and established-account FNR are investigation signals; group composition and scenario support are small and synthetic. No result supports a fairness claim.

## 5. False-positive counts and simulated legitimate value affected

At the selected test threshold, **5 of 951 legitimate wallet-case predictions** are false positives (FPR **0.5258%**). Those false-positive wallet-cases touch **6 distinct generated legitimate transactions** in the pre-analysis snapshot. The gross generated volume exposed under the hypothetical assumption that every associated event is interrupted is **৳103,550**; the mean affected transaction value is **৳17,258.33** and the median is **৳16,592**.

| Cohort dimension | Segment | Legitimate wallet population | False-positive wallet-cases | Distinct cases affected | Simulated legitimate value affected |
|---|---|---:|---:|---:|---:|
| Customer type | Agent | 30 | 0 | 0 | ৳0 |
| Customer type | Individual | 693 | 4 | 4 | ৳70,628 |
| Customer type | Merchant | 228 | 1 | 1 | ৳32,922 |
| Account age | NEW | 29 | 0 | 0 | ৳0 |
| Account age | ESTABLISHED | 121 | 0 | 0 | ৳0 |
| Account age | LONG_TENURE | 801 | 5 | 5 | ৳103,550 |
| Activity | LOW | 496 | 0 | 0 | ৳0 |
| Activity | MEDIUM | 205 | 4 | 4 | ৳102,995 |
| Activity | HIGH | 250 | 1 | 1 | ৳555 |
| Amount profile | LOW_VALUE | 379 | 0 | 0 | ৳0 |
| Amount profile | MEDIUM_VALUE | 298 | 2 | 2 | ৳42,972 |
| Amount profile | HIGH_VALUE | 274 | 3 | 3 | ৳60,578 |

Each dimension is a different view of the same false-positive cases; values **must not be summed across dimensions**. Amounts are deduplicated within each cohort dimension and across the overall population. They are not a loss, actual hold, verified interruption, or actual customer harm. A false positive could cause unnecessary investigation, service delay, intervention, analyst workload, or customer friction, but this synthetic experiment measures none of those real outcomes.

## 6. Intervention-policy counterfactuals

Both strategies use the same validation-selected fraud-risk threshold and held-out test split. No money movement or wallet action occurs.

1. **Aggressive intervention:** treat every wallet-case prediction at or above the risk threshold as an intervention candidate.
2. **Evidence-based with analyst review:** require the risk threshold, positive estimated-exposure proxy `min(reported_amount_bdt, observed_outgoing_amount_bdt)`, graph/cash-out evidence, a validation-derived cash-out urgency cutoff (the validation 75th percentile), and at least two of five listed signals: amount ratio >=2 with a prior relationship; observed outflow; graph/counterparty evidence; elevated predicted cash-out urgency; and observed cash-out. These heuristics overlap and are **not statistically independent evidence**. A qualifying case still requires human analyst review; the prototype does not execute or approve it.

| Test strategy | Candidate wallet-cases | Fraud recall / TPR | Missed frauds / FNR | False positives / FPR | Precision | Simulated legitimate value affected | Assumed workload |
|---|---:|---:|---:|---:|---:|---:|---:|
| Aggressive intervention | 196 | 93.63% | 13 / 6.37% | 5 / 0.53% | 97.45% | ৳103,550 across 6 transactions | 888.50 min; 104 cases |
| Evidence-based with analyst review | 31 | 14.71% | 174 / 85.29% | 1 / 0.11% | 96.77% | ৳36,889 across 2 transactions | 237.75 min; 30 cases |

Assumed workload is `4 minutes/case + 1.5 minutes/unique associated transaction + 0.75 minutes/wallet`, adapted from the project's synthetic investigation-time assumption. It is not measured analyst time. The evidence gate lowers counterfactual false positives, exposed value, and workload in this sample **but misses many more synthetic fraud-labeled wallet-cases**; it is not a recommended production rule. Neither maximizing recall nor minimizing false positives alone is an acceptable objective.

## 7. Validation-threshold diagnostic sweep

These results are on the **validation split used in model/threshold selection** (1,155 wallet-cases; 204 positive, 951 negative); this is not held-out performance. The selected operating threshold is **0.739618**, from the existing validation-F1 model selection. No threshold is chosen using the test set.

| Validation threshold | TP | FP | TN | FN | FPR | FNR | Precision | Simulated legitimate value affected | Assumed workload |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.50 | 195 | 13 | 943 | 4 | 1.36% | 2.01% | 93.75% | ৳184,268 | 939.00 min |
| 0.60 | 195 | 12 | 944 | 4 | 1.26% | 2.01% | 94.20% | ৳176,368 | 932.75 min |
| 0.70 | 193 | 10 | 946 | 6 | 1.05% | 3.02% | 95.07% | ৳171,311 | 922.75 min |
| **0.739618 (selected)** | 193 | 9 | 947 | 6 | 0.94% | 3.02% | 95.54% | ৳162,336 | 920.50 min |
| 0.80 | 189 | 7 | 949 | 10 | 0.73% | 5.03% | 96.43% | ৳133,461 | 895.00 min |
| 0.90 | 176 | 5 | 951 | 23 | 0.52% | 11.56% | 97.24% | ৳105,361 | 843.25 min |

In this synthetic validation sweep, higher thresholds reduce false positives/value/workload and increase missed fraud. This is not an operating recommendation: any future threshold needs an approved cost model, independent validation, and governed pilot.

## 8. Bias-prevention safeguards

- Uses only existing synthetic, non-sensitive operational cohorts; the model's feature list is unchanged.
- Fits activity and amount cohort cut points on training profiles only.
- Uses the model's existing validation-selected threshold for test results and never searches test thresholds.
- Retains small and one-class cohorts with support warnings; suppresses unsupported class-dependent metrics and gaps.
- Emits aggregate-only JSON/CSV, checks the metrics API artifacts for identifier keys, and protects the two fairness read endpoints with role-mapped bearer tokens. There is no hard-coded/default token. The dashboard keeps its token in component memory only.
- Reports policy actions, potential customer-value exposure, and analyst time as counterfactual assumptions. All strategy outputs mark `automatic_execution: false`.
- Presents cohort metrics and gaps neutrally, not as green/red “fair/unfair” decisions.

## 9. Recommended mitigation and production-validation plan

1. Keep recommendations shadow-only. Require documented human review and appeal/override procedures before any consequential action. Never use this synthetic policy comparison to set a real customer hold or denial rule.
2. Obtain institution, privacy, legal, security, and model-risk approval before any real MFS study. Define purpose, minimized fields, retention, independent outcome labeling, appeal routes, and access controls first.
3. Use independently reviewed representative time-based and out-of-family data; measure real analyst workload and verified transaction outcomes. Pre-register cohort metrics, support rules, confidence intervals, action thresholds, acceptable harm, and remediation triggers.
4. Investigate the low-amount-profile and established-account FNR gaps through label quality, scenario coverage, calibration, and feature behavior. Do not change the model solely to improve a synthetic table. Consider threshold review, calibration, better training coverage, scenario balancing, additional validation, borderline human review, and drift monitoring only after an explicit trade-off review.
5. Reassess after drift and each model or policy change. Passing this prototype's demo does not authorize production deployment or provider integration.

## 10. Limitations, reproduction, and artifacts

The test repeats variants of 11 generator families and is not a temporal or new-family evaluation. Labels and cohorts are synthetic and do not establish real population representativeness. No confidence intervals, hypothesis tests, causal evidence, or measure of demographic disparate impact is provided. False-positive values depend on generator labels and a transaction-volume counterfactual. Validation threshold diagnostics share selection data. The HTTP token mapping is a narrow demo RBAC control for the two aggregate read endpoints, not comprehensive production authorization, secrets management, audit logging, or a security certification.

Reproduce from the repository root (the generation step refreshes the seed-42 dataset using the current generator):

```bash
python -m data_generator.generate --seed 42
python -m ml.train --seed 42
python -m ml.evaluate
python -m core.baseline --split test
python -m core.impact_analysis
python -m core.fairness_analysis --thresholds 0.50,0.60,0.70,0.80,0.90
```

The evaluator writes these aggregate-only files under `ml/artifacts/`:

- `fairness_evaluation.json` and `fairness_evaluation.csv`
- `false_positive_impact.json` and `false_positive_impact.csv`

The API exposes aggregate JSON at `/api/metrics/fairness` and `/api/metrics/false-positive-impact`; both require a bearer role with `fairness:read`.

Configure high-entropy tokens on the API server (never in source control or a browser build) by mapping token strings to roles:

```bash
export FLOWFREEZE_RBAC_TOKENS='{"<at-least-32-character-secret>":"fairness_analyst","<another-at-least-32-character-secret>":"model_auditor","<another-at-least-32-character-secret>":"risk_admin"}'
```

Only those three roles have `fairness:read`; configured roles such as `operations_viewer` are denied. Missing/invalid server configuration fails closed (503), a missing/invalid bearer token returns 401, and an unauthorized role returns 403. The dashboard requests the token per session and does not persist it. `risk_admin` remains read-only on these endpoints; the roles imply no permissions on other APIs.
