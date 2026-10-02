# FlowFreeze

FlowFreeze is an AI-assisted fraud containment and fund-flow intelligence prototype for an upay BD sponsored hackathon. It is designed to help an authorized analyst trace suspicious transfers, estimate potentially tainted e-money, anticipate likely next movement, and review a proportionate intervention recommendation.

> **Prototype boundary:** FlowFreeze uses synthetic data and simulates interventions. It does not autonomously confiscate, reverse, refund, or legally freeze money. Any real hold capability requires provider, legal, and regulatory validation.

## Build plan

See [BUILD_PLAN.md](BUILD_PLAN.md) for the phased implementation plan and definition of done.

## Planned stack

- Backend and ML: Python, FastAPI, pandas, scikit-learn, NetworkX
- Frontend: React, Vite, Tailwind CSS
- MVP storage: SQLite
- Demo data: synthetic only

## Safety and data

- Never use real customer data, NID details, wallet numbers, production credentials, or secret keys.
- Keep predictions separate from policy decisions and show evidence and uncertainty.
- Require analyst review for every simulated intervention.
- Clearly label all synthetic metrics; they are not upay production statistics.

## Status

The seeded synthetic data workflow, balance-checked replay, bounded downstream graph tracing, proportional reported-fund attribution, Step 6 intervention-policy prototype, Step 7 local API/audit workflow, and Step 8 analyst frontend are implemented. **Roadmap Step 5 (fraud and next-move model training/evaluation) remains outstanding**, so the frontend marks scores unavailable by default and recommendations fail closed to monitoring/review when scores are not supplied. The score controls are only for clearly labeled illustrative demo inputs.

## Generate demo data

Requires Python 3.11 or later. In PowerShell, create the environment and install the pinned project dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The generator itself uses only Python's standard library, so it can also run before installing the project dependencies once Python is available.

```powershell
python -m data_generator.generate --seed 42
```

This writes `transactions.csv`, `wallets.csv`, `incidents.csv`, `ground_truth.csv`, `generation_metadata.json`, and `flowfreeze.db` under `data/`. Reusing the same seed reproduces the profile attributes and scenario data. See [data/README.md](data/README.md) and [the data dictionary](docs/DATA_DICTIONARY.md) for details.

The generator produces 100 varied cases per scenario family by default, with benign historical activity and case-level train/validation/test splits. This supports initial synthetic model experiments, but it is **not evidence of upay production performance**. Results will depend on the synthetic assumptions and must be labeled accordingly.

## Replay or reset a scenario

Replay only the events visible by the incident's `analysis_at` time:

```powershell
python -m core.simulator SCN-06-FANOUT-CASHOUT-0001
```

Reset all synthetic CSVs and the local database to the default seed:

```powershell
python -m demo.reset_demo --seed 42
```

Trace downstream paths visible at the incident analysis time:

```powershell
python -m core.graph SCN-06-FANOUT-CASHOUT-0001 --hops 5 --window-minutes 30
```

Trace amounts are gross transaction amounts; the graph does not label every amount on a path as tainted. Proportional attribution belongs to the next processing layer.

Estimate proportional reported-fund attribution at the same incident analysis time:

```powershell
python -m core.taint SCN-06-FANOUT-CASHOUT-0001
```

The estimate and its assumptions are described in [TAINT_METHODOLOGY.md](docs/TAINT_METHODOLOGY.md). It is not a fraud finding or a determination of ownership.

## Build a simulated intervention recommendation

The policy in `core/policy.yaml` is JSON syntax, which is also valid YAML, so the policy can be loaded without an extra parser dependency. This CLI accepts optional scores so the policy can be explored before the ML models are implemented; omitted scores are treated as unavailable and fail closed to monitoring/review.

```powershell
python -m core.intervention SCN-06-FANOUT-CASHOUT-0001 --fraud-risk 0.82 --p-forward 0.20 --p-cashout 0.65 --p-no-movement 0.15
```

The result shows the policy version, evidence transaction IDs, potential collateral, thresholds, and an action proposal for each wallet with a positive taint estimate. It never changes a balance or contacts a provider. Wrong-recipient disputes are routed to review. See [INTERVENTION_POLICY.md](docs/INTERVENTION_POLICY.md).

## Start the backend API

Generate the synthetic database first, then run the local API from the repository root:

```powershell
python -m uvicorn backend.main:app --reload
```

Interactive API docs are at `http://127.0.0.1:8000/docs`; endpoints and request examples are listed in [API.md](docs/API.md). The server is configured for local frontend development. Do not expose this synthetic demo API publicly. The development-only `POST /api/demo/reset` regenerates the SQLite database and clears its local decision/audit history.

## Start the analyst frontend

With the API running in a separate terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. The frontend reads `VITE_API_BASE_URL` from `frontend/.env.local` when provided; its default is the local API above. The demo entry screen is not authentication. See the [frontend setup](frontend/README.md) for details.
