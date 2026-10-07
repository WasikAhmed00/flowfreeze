# Real-data fraud model MVP

FlowFreeze now supports an optional fraud classifier trained on a bounded sample of the public `Fraud.csv` transaction dataset. The MVP defaults to **10,000 rows**, not the full multi-million-row source dataset.

## Setup and training

Place the dataset at `data/ml/Fraud.csv`, or provide a path with `FLOWFREEZE_REAL_DATA_PATH` / `--data-path`:

```bash
python -m ml.train_real --data-path data/ml/Fraud.csv --max-rows 10000 --seed 42
python -m ml.predict SCN-02-FANOUT-0001
```

The command writes:

- `ml/artifacts/real_fraud_model.joblib`
- `ml/artifacts/real_preprocessor.joblib`
- `ml/artifacts/real_model_metadata.json`

The model selection candidates are balanced logistic regression and random forest; selection is by validation PR-AUC, then ROC-AUC. The preferred split is chronological by `step` (60% train, 20% validation, 20% held-out test). Small or single-class time bins use a documented stratified fallback.

## Features and leakage controls

Input features are exactly:

`step`, `type`, `amount`, `oldbalanceOrg`, `newbalanceOrig`, `oldbalanceDest`, `newbalanceDest`.

`isFraud` is the label. `nameOrig` and `nameDest` are excluded identifiers. `isFlaggedFraud` is excluded because it is a rule-generated field; it is not treated as an independent predictive signal. Numeric features use train-fitted median imputation and scaling. `type` uses train-fitted one-hot encoding with unknown-category handling.

## FlowFreeze mapping

For each visible synthetic `TransactionEvent`:

| FlowFreeze field | Public-model field |
|---|---|
| elapsed transaction hour from scenario start | `step` |
| `transaction_type` (`cashout`, `transfer`, `merchant_payment`) | `type` (`CASH_OUT`, `TRANSFER`, `PAYMENT`) |
| `amount` | `amount` |
| `sender_balance_before` | `oldbalanceOrg` |
| `sender_balance_after` | `newbalanceOrig` |
| `receiver_balance_before` | `oldbalanceDest` |
| `receiver_balance_after` | `newbalanceDest` |

The transaction classifier is converted to wallet risk using `0.6 * max(transaction risk) + 0.4 * mean(transaction risk)` over each wallet's visible incoming/outgoing transactions. This remains bounded in `[0, 1]` and avoids treating one extreme transaction as the entire wallet score.

The existing next-move model remains separate and explicitly synthetic. It is never fabricated from the fraud classifier.

## Data status and safety

The API reports the scenario data and fraud model sources independently:

- FlowFreeze incident, graph, taint, and simulator data: **synthetic**.
- Fraud model: **public transaction dataset-trained** when artifacts are installed.
- The public dataset is **not upay BD production/customer data** and the score is not a production probability.
- Scores are decision support only. Analyst review and simulated-action safeguards remain in place; no wallet freeze, transfer, reversal, or other financial action is executed automatically.

If the real artifact is missing, the API returns `model_status: unavailable` and does not invent a public-data score. Existing synthetic-model behavior remains available when its artifacts are installed.

## Limitations

The source data is a simulated public dataset with a different population, label process, transaction vocabulary, and balance behavior from any real MFS deployment. Results on the 10,000-row MVP sample are not production validation. Thresholds and metrics must be re-estimated on representative, governed, consented data before operational use.
