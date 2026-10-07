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
| `GET` | `/api/incidents` | Paginated incident list; optional `scenario_type` and `status` filters. |
| `GET` | `/api/incidents/{scenario_id}` | Incident metadata and scenario record counts. |
| `GET` | `/api/analysis/{scenario_id}` | Time-bounded replay, graph trace, taint estimate, and policy recommendation. Optional `fraud_risk` and all three next-move probability query values can be supplied. |
| `POST` | `/api/decisions` | Append an analyst approve/reject/modify decision with reason, actor, and bounded simulated amount. |
| `POST` | `/api/decisions/{decision_id}/feedback` | Append one validated usefulness, trace-accuracy, confidence, and reason feedback record. Synthetic demo data only; update/delete are blocked. |
| `GET` | `/api/decisions` | Read-only audit history, optionally filtered by `scenario_id`. |
| `POST` | `/api/simulation/{decision_id}` | Record one synthetic outcome estimate for a prior decision; does not alter balances. |
| `GET` | `/api/metrics` | Synthetic dataset counts, decision counts, aggregate simulation estimates, held-out ML metrics, end-to-end baseline results, and the financial-impact artifact when generated. |
| `GET` | `/api/metrics/shadow-mode` | Synthetic shadow-mode events and heuristic metrics plus a separately aggregated local analyst-feedback summary. |
| `GET` | `/api/metrics/business-impact` | Synthetic business-impact simulation results and assumptions. |
| `GET` | `/api/metrics/impact/{scenario_id}` | Calculate a selected synthetic case's direct-recipient vs. multi-hop exposure comparison and event-time response-delay curve. |
| `GET` | `/api/demo` | List seeded demo scenarios. |
| `POST` | `/api/demo/reset?seed=42` | Regenerate synthetic CSV/SQLite data in development mode using the default `data/flowfreeze.db` location. This replaces the database and clears its local audit history. |

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

- The API has no production authentication or provider integration; bind it to a trusted local development environment only.
- There are no wallet-control routes. Decision approval never changes a ledger or contacts a wallet.
- Audit entries are append-only through the API. A demo reset intentionally replaces the SQLite file, including local audit history.
- Analyst feedback is stored in a SQLite table with update/delete rejection triggers; it remains synthetic demo feedback and is not a regulated record. Shadow event operator/outcome fields are null in the synthetic simulation.
- After running `python -m ml.train`, `/api/analysis/{scenario_id}` automatically includes locally trained synthetic wallet scores. The metrics endpoint serves the tracked held-out metrics file even when ignored local model artifacts are absent. Missing model artifacts leave scores unavailable; caller-supplied scores are labeled illustrative.
- ML scores, performance metrics, and recommendations are synthetic and advisory. See `docs/MODEL_CARD.md` and `docs/RESPONSIBLE_AI.md`.
- The end-to-end comparison is generated from the held-out test cases using an instant-action counterfactual assumption; it is not observed value preserved. See `docs/END_TO_END_EVALUATION.md`.
- Never use real customer information or production credentials with this prototype.
