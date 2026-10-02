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

Steps 1–5 are implemented: the project has a seeded synthetic dataset, balance-checked replay, bounded downstream graph tracing, and proportional reported-fund attribution with wallet-level collateral estimates.

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

The current generated set has eight canonical scenarios. It is enough to exercise the data shape and demo paths; it is **not large enough to claim model performance**. We will expand and validate the synthetic population before training models.

## Replay or reset a scenario

Replay only the events visible by the incident's `analysis_at` time:

```powershell
python -m core.simulator SCN-06-FANOUT-CASHOUT
```

Reset all synthetic CSVs and the local database to the default seed:

```powershell
python -m demo.reset_demo --seed 42
```

Trace downstream paths visible at the incident analysis time:

```powershell
python -m core.graph SCN-06-FANOUT-CASHOUT --hops 5 --window-minutes 30
```

Trace amounts are gross transaction amounts; the graph does not label every amount on a path as tainted. Proportional attribution belongs to the next processing layer.

Estimate proportional reported-fund attribution at the same incident analysis time:

```powershell
python -m core.taint SCN-06-FANOUT-CASHOUT
```

The estimate and its assumptions are described in [TAINT_METHODOLOGY.md](docs/TAINT_METHODOLOGY.md). It is not a fraud finding or a determination of ownership.
