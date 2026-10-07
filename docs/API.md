# FlowFreeze Local API

Run from the repository root after generating demo data:

```powershell
python -m uvicorn backend.main:app --reload
```

OpenAPI documentation is served at `/docs`. All endpoints are local demo APIs and all generated data is synthetic.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service status and synthetic-only boundary. |
| `POST` | `/api/transactions` | Validate, run one event through the extended analysis pipeline, and persist it; returns graph context, heuristic risk, taint estimate, alerts and next-move prediction. Duplicate IDs return `409`. |
| `GET` | `/api/transactions` | Read the newest persisted stream events (`limit` 1–200). |
| `POST` | `/api/transactions/simulate` | Generate 1–20 synthetic MFS-shaped events through the same stream processor (optional deterministic `seed`). |
| `POST` | `/api/cases` | Create a case; risk may be inherited from a linked stream transaction. |
| `GET` | `/api/cases` | List cases with `limit`, `offset`, and optional `status` filter. |
| `GET` | `/api/cases/{case_id}` | Read one case by its `FF-00000001` identifier. |
| `PATCH` | `/api/cases/{case_id}` | Update risk, investigator, status, title or notes. |
| `GET` | `/api/incidents` | Paginated incident list; optional `scenario_type` and `status` filters. |
| `GET` | `/api/incidents/{scenario_id}` | Incident metadata and scenario record counts. |
| `GET` | `/api/analysis/{scenario_id}` | Time-bounded replay, graph trace, taint estimate, and policy recommendation. Optional `fraud_risk` and all three next-move probability query values can be supplied. |
| `POST` | `/api/decisions` | Append an analyst approve/reject/modify decision with reason, actor, and bounded simulated amount. |
| `POST` | `/api/decisions/{decision_id}/feedback` | Append one validated usefulness, trace-accuracy, confidence, and reason feedback record. Synthetic demo data only; update/delete are blocked. |
| `GET` | `/api/decisions` | Read-only audit history, optionally filtered by `scenario_id`. |
| `POST` | `/api/simulation/{decision_id}` | Record one synthetic outcome estimate for a prior decision; does not alter balances. |
| `GET` | `/api/metrics` | Synthetic dataset and decision metrics plus `operational` API request/latency/error counters, stream totals/alerts, and case totals. |
| `GET` | `/api/metrics/shadow-mode` | Synthetic shadow-mode events and heuristic metrics plus a separately aggregated local analyst-feedback summary. |
| `GET` | `/api/metrics/business-impact` | Synthetic business-impact simulation results and assumptions. |
| `GET` | `/api/metrics/impact/{scenario_id}` | Calculate a selected synthetic case's direct-recipient vs. multi-hop exposure comparison and event-time response-delay curve. |
| `GET` | `/api/demo` | List seeded demo scenarios. |
| `POST` | `/api/demo/reset?seed=42` | Regenerate synthetic CSV/SQLite data in development mode using the default `data/flowfreeze.db` location. This replaces the database and clears its local audit history. |

### Transaction event example

```json
{
  "transaction_id": "partner-event-0001",
  "timestamp": "2026-10-07T10:00:00Z",
  "sender_wallet": "synthetic-wallet-01",
  "receiver_wallet": "synthetic-wallet-02",
  "amount_bdt": "1250.00",
  "transaction_type": "transfer",
  "channel": "synthetic-adapter"
}
```

`amount` is accepted as an alias for `amount_bdt`. Send stable event IDs for deduplication. The current adapter accepts synthetic/de-identified wallet references and emits explicit synthetic heuristic outputs; it does not authenticate a partner, connect to Upay or another MFS provider, or trigger wallet actions. A production connector requires partner-approved authentication, schemas, retry/idempotency policy, privacy review, and load/security testing.

`POST /api/transactions/simulate` powers the dashboard's **Live Simulation** control; its events follow the same ingestion path. Stream subgraphs are bounded to a recent 10-minute local neighborhood. Taint is an illustrative risk-weighted amount estimate, not the existing ledger replay's proportional taint calculation. Predictions are heuristic, not calibrated model probabilities.

### Operational readiness and scale benchmark

`/health` returns `status`, `database`, `synthetic_data_only`, and `automatic_wallet_actions`. `/api/metrics.operational` reports request counts and process-local response-time/error counters alongside stream and case totals; these counters reset at process restart and are not a durable monitoring backend. Run `python scripts/benchmark_scalability.py` to replay a deterministic 10,000-wallet synthetic network at 1K, 10K, 50K, and 100K events and sample API latency. See `docs/SCALABILITY_BENCHMARK.md` for the measured run and limitations.

### Financial-impact analysis

Run `python -m data_generator.generate --seed 42` followed by `python -m core.impact_analysis` to create `ml/artifacts/impact_analysis.json` and `ml/artifacts/impact_analysis.csv`. `/api/metrics` serves the aggregate JSON artifact when present. The selected-case route replays the SQLite ledger directly and includes the incident snapshot, direct-vs-traced amounts, trace paths, and default 0/5/10/15/30/60-minute cutoffs. At each cutoff, comparisons and paths use the same event-time-bounded replay; future synthetic events are not included early.

All such metrics are synthetic accounting estimates. Exposure is remaining proportional taint plus taint attributed to observed cash-outs, not actual loss or recovery. The delay points are hypothetical replay cutoffs, not measured operating response times. See `docs/END_TO_END_EVALUATION.md` for definitions and the seed-42 results.

`downstream_hops_identified` counts unique reachable non-cash-out transaction edges; `maximum_downstream_depth` is the transfer-hop distance to the furthest digital wallet. Terminal cash-out destinations are excluded from wallet depth and reported through cash-out counts and values.

### Analyst decision example

```json
{
  "scenario_id": "SCN-06-FANOUT-CASHOUT-0001",
  "wallet_id": "SCN-06-FANOUT-CASHOUT-0001-W1",
  "decision": "modify",
  "proposed_amount_bdt": "2500.00",
  "reason": "Reduce the simulated amount pending additional review.",
  "actor": "demo_analyst"
}
```

Rejected decisions must use amount zero. Approved or modified amounts must be positive and no greater than the current replay balance or policy cap. `POST /api/simulation/{decision_id}` can be called only once per decision; it records estimated tainted value preserved and estimated legitimate value affected. These values are scenario calculations, not actual funds or production statistics.

## Safety and deployment limits

- The API has no comprehensive production authentication or provider integration. Only the two aggregate fairness read endpoints require the narrow operator-mapped bearer RBAC described below; bind this prototype to a trusted development environment only.
- There are no wallet-control routes. Decision approval never changes a ledger or contacts a wallet.
- Audit entries are append-only through the API. A demo reset intentionally replaces the SQLite file, including local audit history.
- Analyst feedback is stored in a SQLite table with update/delete rejection triggers; it remains synthetic demo feedback and is not a regulated record. Shadow event operator/outcome fields are null in the synthetic simulation.
- After running `python -m ml.train`, `/api/analysis/{scenario_id}` automatically includes locally trained synthetic wallet scores. The metrics endpoint serves the tracked held-out metrics file even when ignored local model artifacts are absent. Missing model artifacts leave scores unavailable; caller-supplied scores are labeled illustrative.
- ML scores, performance metrics, and recommendations are synthetic and advisory. See `docs/MODEL_CARD.md` and `docs/RESPONSIBLE_AI.md`.
- The end-to-end comparison is generated from the held-out test cases using an instant-action counterfactual assumption; it is not observed value preserved. See `docs/END_TO_END_EVALUATION.md`.
- Never use real customer information or production credentials with this prototype.


### Protected Responsible AI / fairness metrics

| Method | Path | Purpose / access |
|---|---|---|
| `GET` | `/api/metrics/fairness` | Aggregate test-split subgroup error metrics, validation-only threshold diagnostics, cohort gaps and intervention counterfactuals. Requires bearer role scope `fairness:read`. |
| `GET` | `/api/metrics/false-positive-impact` | Aggregate false-positive counts, rates, generated legitimate transaction-value exposure, mean/median event values, and affected cases/value by synthetic cohort. Requires bearer role scope `fairness:read`. |

Both endpoints return only JSON aggregates and reject artifacts that are not marked synthetic or contain identifier keys. They fail closed with `503` when the server RBAC configuration or report artifact is unavailable/invalid, return `401` for a missing/invalid token, and `403` for a configured role without the read scope. They do not return wallet-, transaction-, or scenario-level records.

Run the analysis from the repository root after generating the synthetic data and training the project models:

```bash
python -m data_generator.generate --seed 42
python -m ml.train --seed 42
python -m core.fairness_analysis
```

This writes `fairness_evaluation.json`, `fairness_evaluation.csv`, `false_positive_impact.json`, and `false_positive_impact.csv` under `ml/artifacts/`. Configure `FLOWFREEZE_RBAC_TOKENS` on the API server as JSON mapping high-entropy bearer tokens (at least 32 characters) to `fairness_analyst`, `model_auditor`, or `risk_admin`. All three roles are read-only for these endpoints; there is no default token. Do not put server tokens in source control or frontend build variables. The dashboard asks the authorized reader to enter a token, retains it only in component memory, and sends it in an Authorization header. See `docs/FAIRNESS_AND_HARM.md` for the cohort definitions, sample-support rules, measured synthetic results, validation/test discipline, policy comparison, and limitations.
