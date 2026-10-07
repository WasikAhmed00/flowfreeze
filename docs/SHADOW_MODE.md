# FlowFreeze Shadow Mode

> **Synthetic shadow-mode simulation — not a real pilot or production deployment.** The prototype has no payment-system connection, provider integration, customer contact channel, or financial-action capability.

## How shadow mode works

A governed future deployment would produce two independent records for the same pseudonymous case: (1) the current process/operator decision, sourced from the partner's authorized case system, and (2) a FlowFreeze recommendation, computed separately and made visible only for evaluation. In this repository, the simulator demonstrates only the FlowFreeze-side record and a synthetic current-process comparator. It leaves operator decisions, confirmed outcomes, operator timestamps, analyst review time, and agreement unavailable/null. It does not infer actual operator activity from generated labels.

FlowFreeze records what it **would recommend**. It cannot freeze accounts, block or reverse transfers, move money, contact customers, or invoke a financial/provider API. A future true shadow deployment must technically enforce read-only credentials, network allow-lists, no write routes to provider systems, and a kill switch controlled by the partner.

## Event schema

`case_id` is a stable pseudonymous case key (the simulation hashes the synthetic scenario ID); it is not a customer identifier. Never put names, phone numbers, wallet IDs, or direct identifiers in the shadow event stream.

| Field | Meaning |
|---|---|
| `case_id` | Pseudonymous join key for the evaluation case. |
| `model_version` | Model/rule and configuration version; simulation identifies its output as a transparent heuristic. |
| `risk_score` | FlowFreeze-side synthetic risk score on [0,1], if available. |
| `predicted_next_move` | Predicted move class (cash-out, forward, or no movement), with confidence/source recorded in a production schema. |
| `trace_depth` | Maximum downstream hop depth found within configured limits. |
| `estimated_exposure` | Estimated potentially exposed amount and currency; synthetic records use BDT. |
| `recommendation` | Advisory output, never an instruction sent to a payment system. |
| `actual_operator_decision` | Partner-sourced decision if authorized and available; null in this simulation. |
| `actual_outcome` | Independently confirmed case outcome; null until validated. |
| `decision_timestamp` | Timestamp of the existing operational decision; null in this simulation. |
| `flowfreeze_decision_timestamp` | Time the advisory output was produced; synthetic data uses the case analysis timestamp. |
| `analyst_review_time` | Measured review duration; null without an actual, consented analyst trial. |
| `recommendation_agreement` | Agreement result computed only when a real paired operator decision exists; null in this simulation. |
| `false_positive` / `false_negative` | Evaluation flags only after an agreed, independently confirmed label definition. Synthetic run uses generated labels and clearly identifies them as such. |
| `estimated_exposure_difference` | FlowFreeze estimate minus the synthetic direct-recipient baseline for the same case in this simulation. A real pilot must use an agreed, comparable partner baseline; otherwise this field remains null. |

All shadow events include `synthetic`, `automatic_execution: false`, and `financial_actions_executed: 0` in this simulation. JSON and CSV outputs are generated under `ml/artifacts/` by `python -m core.shadow_mode`.

## Synthetic simulation and pilot KPIs

The simulator compares a disclosed direct-recipient observable-flow heuristic with a bounded multihop observable-flow heuristic. It uses generated fraud/taint labels solely as synthetic reference outcomes. Precision, recall and average precision (PR-AUC proxy) therefore describe the synthetic heuristics against generator labels, not production model quality. Time-to-useful-signal uses generated event timestamps; time-to-trace uses report-to-analysis timestamps; workload applies the previously disclosed synthetic review-time model. Simulated prevented exposure is an immediate-intervention counterfactual and is **not actual prevented loss**.

Analyst agreement, overrides, confidence, and recommendation usefulness are not available from simulated data. When an analyst enters feedback in the prototype, the API aggregates the recorded demo feedback separately; that is still not a representative or production pilot sample. Pilot targets are intentionally null/configurable in `core/pilot_targets.json` with the status **TARGET TO BE AGREED DURING PILOT**. A partner-approved target can be entered there or supplied to the CLI using `--targets <path>`; values are not silently replaced with defaults.

API: `GET /api/metrics/shadow-mode`. It returns the synthetic case events and simulator KPIs, along with a separate summary of locally recorded analyst feedback.

## Feedback audit trail

Feedback is linked to a recorded synthetic analyst decision. The API validates fixed response categories and appends one row to SQLite `analyst_feedback`; the table rejects update/delete operations and permits one feedback row per decision. It records the actor, UTC timestamp, synthetic flag, useful/not-useful response, trace accuracy, confidence, and optional short reason. This local demo log is not a regulated record and must not receive personal or production information.

## Safety and privacy requirements before a real shadow phase

- Written partner authorization and approved purpose, lawful basis, retention, access roles and data-processing terms.
- Partner-owned pseudonymization/tokenization; FlowFreeze should not receive direct customer identifiers.
- Read-only case/event source; no wallet-control, payment write credential, outbound customer messaging, or transaction action path.
- Data minimization, encryption, access logging, least privilege, defined deletion, incident response and security review.
- Independent outcome-labeling protocol, model/configuration versioning, threshold governance, drift/error monitoring and fairness review.
- Paired event IDs and synchronized timestamps to compare decisions without changing the current process.
- A named partner operator can pause ingestion and evaluation immediately; stop rules are agreed before launch.

See [PILOT_PLAN.md](PILOT_PLAN.md) for staged validation and partner-agreed target setting.
