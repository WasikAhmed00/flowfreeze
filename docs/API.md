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
| `GET` | `/api/decisions` | Read-only audit history, optionally filtered by `scenario_id`. |
| `POST` | `/api/simulation/{decision_id}` | Record one synthetic outcome estimate for a prior decision; does not alter balances. |
| `GET` | `/api/metrics` | Synthetic dataset counts, decision counts, aggregate simulation estimates, and held-out ML metrics when generated. |
| `GET` | `/api/demo` | List seeded demo scenarios. |
| `POST` | `/api/demo/reset?seed=42` | Regenerate synthetic CSV/SQLite data in development mode using the default `data/flowfreeze.db` location. This replaces the database and clears its local audit history. |

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
- After running `python -m ml.train`, `/api/analysis/{scenario_id}` automatically includes locally trained synthetic wallet scores. The metrics endpoint serves the tracked held-out metrics file even when ignored local model artifacts are absent. Missing model artifacts leave scores unavailable; caller-supplied scores are labeled illustrative.
- ML scores, performance metrics, and recommendations are synthetic and advisory. See `docs/MODEL_CARD.md` and `docs/RESPONSIBLE_AI.md`.
- Never use real customer information or production credentials with this prototype.
