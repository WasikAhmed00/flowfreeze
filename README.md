# FlowFreeze

FlowFreeze is an AI-assisted fraud containment and fund-flow intelligence prototype for an upay BD sponsored hackathon. It is designed to help an authorized analyst trace suspicious transfers, estimate potentially tainted e-money, anticipate likely next movement, and review a proportionate intervention recommendation.

> **Prototype boundary:** FlowFreeze uses synthetic data and simulates interventions. It does not autonomously confiscate, reverse, refund, or legally freeze money. Any real hold capability requires provider, legal, and regulatory validation.

## Build plan

See [BUILD_PLAN.md](BUILD_PLAN.md) for the phased implementation plan and definition of done.

For a public synthetic demo, use the explicit [Render free-tier deployment guide](docs/RENDER_FREE_TIER.md).

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

Steps 0–10 are implemented for the synthetic hackathon prototype. Model scores are synthetic advisory inputs; policy checks and analyst review remain separate. Read the [model card](docs/MODEL_CARD.md), [responsible AI notes](docs/RESPONSIBLE_AI.md), [limitations](docs/LIMITATIONS.md), and [end-to-end evaluation report](docs/END_TO_END_EVALUATION.md) before interpreting results.

## Start the complete local demo (Windows)

With Python 3.11+ and Node.js 20+ installed, run this from PowerShell at the repository root:

```powershell
.\demo\start_demo.ps1
```

On first run, the script creates `.venv` if needed, installs Python/frontend dependencies if missing, generates the seeded synthetic data if any required file is missing, trains local models if model files are missing, and starts the API/frontend on `127.0.0.1`. It writes service logs and process IDs under the ignored `demo/.runtime/` folder. Open `http://127.0.0.1:5173`; use `http://127.0.0.1:8000/docs` for the local API docs. Stop both services with:

```powershell
.\demo\stop_demo.ps1
```

To reset the generated SQLite database and its local audit history, run:

```powershell
.\.venv\Scripts\python.exe -m demo.reset_demo --seed 42
```

Reset does not retrain the models. The synthetic generator and benchmark are deterministic for a fixed seed, while local timing depends on the computer. See the [judge demo script](demo/DEMO_SCRIPT.md) for the walkthrough and reset checklist.

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

## Train and evaluate the synthetic models

After generating data and installing requirements, train the fraud and next-move models using the fixed case-level splits:

```powershell
python -m ml.train --seed 42
python -m ml.evaluate
python -m ml.explain --rows 825
python -m ml.predict SCN-06-FANOUT-CASHOUT-0001
python -m core.baseline --split test
```

Training writes local ignored `.joblib` model artifacts and a reviewable `ml/artifacts/metrics.json`. Model scores are automatically available to the analysis API when those local model files exist. The validation split selects the fraud model/threshold and fits next-move probability calibration; held-out test results are reported separately. `ground_truth.csv` supplies labels only and is not used by inference feature generation. Metrics are limited to held-out variants from the same eight synthetic scenario families and do not establish real-world or upay BD performance; details are in the [model card](docs/MODEL_CARD.md).

The Step 9 benchmark runs both direct-recipient-only and FlowFreeze policy strategies over the same held-out cases. It writes `ml/artifacts/end_to_end_metrics.json`, which the Evaluation page displays alongside its assumptions. Value preserved and legitimate value affected are counterfactual estimates based on generated remaining-taint labels and an instant-action assumption; they are not observed outcomes. See [the benchmark report](docs/END_TO_END_EVALUATION.md).

## Build a simulated intervention recommendation

The policy in `core/policy.yaml` is JSON syntax, which is also valid YAML, so the policy can be loaded without an extra parser dependency. This CLI accepts optional scores for independent policy exploration; omitted scores are unavailable and fail closed to monitoring/review. The API pipeline uses local trained synthetic model artifacts automatically when present.

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

## Deploy on Render's free tier

The repository includes `render.yaml` plus `scripts/render-build.sh` and
`scripts/render-start.sh`. The API build regenerates the seeded synthetic
database and trains the model artifacts before startup; the static frontend is
built with an explicit API URL. Public deployments are read-only by default,
and the free tier can sleep or lose its ephemeral SQLite data after restart.
See [docs/RENDER_FREE_TIER.md](docs/RENDER_FREE_TIER.md) for the required
environment variables and live-demo expectations.
