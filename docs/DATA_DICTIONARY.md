# FlowFreeze Synthetic Data Dictionary

All records are synthetic. Identifiers must be generated demo IDs and must never encode real wallet, phone, NID, or customer identifiers. Store timestamps in ISO 8601 UTC; render them in the UI with an explicit local timezone when needed. Money fields use Bangladeshi taka (BDT/৳) as non-negative decimal amounts; implementation should use integer poisha or a decimal type rather than binary floating point for money arithmetic.

## `transactions.csv`

One row per synthetic transfer or cash-out event.

| Field | Type | Meaning |
|---|---|---|
| `transaction_id` | string | Unique synthetic event ID. |
| `timestamp` | ISO 8601 datetime | Event time in UTC. |
| `sender_wallet` | string | Synthetic sending wallet or agent ID. |
| `receiver_wallet` | string | Synthetic receiving wallet or cash-out destination ID. |
| `amount` | decimal/integer minor units | Transfer amount in BDT. |
| `transaction_type` | category | For example `transfer`, `cashout`, `merchant_payment`, `cashin`. |
| `channel` | category | Synthetic channel label, not a real provider integration. |
| `agent_id` | nullable string | Synthetic agent ID when relevant. |
| `location` | nullable string | Coarse generated label only; no real customer location. |
| `sender_balance_before` | decimal/integer minor units | Sender balance immediately before event. |
| `sender_balance_after` | decimal/integer minor units | Sender balance immediately after event. |
| `receiver_balance_before` | decimal/integer minor units | Receiver balance immediately before event. |
| `receiver_balance_after` | decimal/integer minor units | Receiver balance immediately after event. |
| `scenario_id` | string | Synthetic scenario grouping key; evaluation metadata, not a model feature. |

## `wallets.csv`

One row per synthetic wallet or agent.

| Field | Type | Meaning |
|---|---|---|
| `wallet_id` | string | Unique synthetic wallet/agent ID. |
| `account_age` | integer | Generated account age in days at scenario start. |
| `customer_type` | category | Synthetic profile such as `individual`, `merchant`, or `agent`. |
| `baseline_balance` | decimal/integer minor units | Generated starting balance in BDT. |
| `average_transaction_amount` | decimal/integer minor units | Generated historical average in BDT. |
| `transaction_frequency` | decimal | Generated historical transactions per day (synthetic profile attribute). |
| `normal_active_hours` | string/category | Synthetic usual activity window. |
| `usual_transaction_types` | category/list | Generated normal event types. |
| `scenario_id` | string | Synthetic scenario grouping key; evaluation metadata, not a model feature. |

## `incidents.csv`

One row per synthetic reported case.

| Field | Type | Meaning |
|---|---|---|
| `incident_id` | string | Unique synthetic case ID. |
| `reported_transaction_id` | string | Transaction that initiated the report. |
| `reported_at` | ISO 8601 datetime | Time the report is received. |
| `analysis_at` | ISO 8601 datetime | Synthetic snapshot time for graph/risk analysis; future transactions must be excluded from inference at this time. |
| `reported_amount` | decimal/integer minor units | Amount associated with report in BDT. |
| `incident_type` | category | For example `suspected_fraud` or `wrong_recipient_dispute`; these are distinct case types. |
| `scenario_type` | category | Synthetic scenario family used for stratified case-level data splits. |
| `status` | category | Workflow status, for example `new`, `analyzing`, `review_pending`, `resolved`. |
| `scenario_id` | string | Synthetic scenario grouping key. |

## `ground_truth.csv`

One row per wallet per incident scenario. Generator/evaluation labels only. Do not expose these as production-like features or use future outcomes as model inputs.

| Field | Type | Meaning |
|---|---|---|
| `scenario_id` | string | Synthetic scenario grouping key. |
| `scenario_type` | category | Synthetic scenario family. |
| `split` | category | Scenario-instance assignment to `train`, `validation`, or `test`; every row for a scenario stays in one split. Evaluation metadata only. |
| `wallet_id` | string | Synthetic wallet represented by this label row. |
| `fraud_flag` | boolean | Whether the generated scenario is labeled fraudulent. |
| `fraud_source_wallet` | string | Generated wallet designated as the source. |
| `tainted_amount` | decimal/integer minor units | Ground-truth tainted amount in BDT for evaluation. |
| `hop_number` | integer | Generated path depth from the reported transfer. |
| `cashout_flag` | boolean | Whether the generated funds are cashed out. |
| `expected_next_action` | category | Ground-truth next event class for evaluation, such as `forward`, `cashout`, or `no_movement`. |

`hop_number` is relative to the direct recipient at `analysis_at`; `-1` means the wallet is not reachable in the observed graph. `fraud_flag` is a wallet-level label indicating that the wallet is part of the generated fraud-linked flow. `tainted_amount` is estimated for evaluation from generated transfer events visible at `analysis_at`.

## Modeling and evaluation rules

- Split train/validation/test by scenario or time, not by randomly splitting rows from the same flow across sets.
- Exclude `scenario_id`, ground-truth taint/fraud labels, and future events from input features unless explicitly justified for a separate offline-only experiment.
- Define the prediction timestamp and label window before feature generation.
- Record random seed and generator configuration so reported metrics can be reproduced.
- Synthetic distributions are design assumptions and are not evidence of actual upay customer behavior.
- `ml.features.build_decision_features` builds inference inputs without opening `ground_truth.csv`; offline training joins the labels only after the input feature table has been constructed.
- The baseline model uses behavior-only fields: 18 numeric and 2 categorical features. Identifiers, split assignments, scenario-family keys, labels, graph reachability, incident-role flags, customer roles, profile balances, and post-analysis outcomes are excluded. Features are aggregated only through `analysis_at`.
- The default case-level split includes variants of each of the eleven scenario families in train, validation, and test. This prevents the same incident case from crossing splits but does not measure generalization to a new scenario family or time period.
- See `docs/MODEL_CARD.md` for the target definitions, model selection, calibration, reported metrics, and limitations.
