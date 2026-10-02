# FlowFreeze MVP Architecture

## Design goal

Keep transaction data, graph tracing, taint attribution, model predictions, intervention policy, and analyst decisions in separate layers. This makes recommendations easier to explain and keeps a statistical prediction from silently becoming an action.

## End-to-end flow

```text
Synthetic scenario generator
          ↓
CSV / SQLite data layer
          ↓
Incident analysis pipeline
  ├─ feature extraction → fraud risk scoring
  ├─ transaction graph → downstream trace / cash-out paths
  ├─ proportional taint attribution
  └─ next-move prediction
          ↓
Configurable intervention policy
          ↓
Evidence-backed recommendation
          ↓
Analyst review and decision
          ↓
Simulated outcome + audit record
          ↓
Baseline comparison and metrics
```

## Components mapped to the requested repository

| Component | Responsibility |
|---|---|
| `data_generator/` | Generate seeded wallets, transactions, incidents, scenario labels, and ground truth. |
| `data/` | Store generated CSVs and local SQLite database; generated/local files should be ignored where appropriate. |
| `backend/db.py` | Resolve the configured SQLite path and provide row-based connections to the generated database. |
| `core/simulator.py` | Replay a scenario in event-time order, validate balance chains, enforce an `as_of` cutoff, and collect cash-out events. |
| `demo/reset_demo.py` | Recreate CSV and SQLite demo state from the configured seed. |
| `ml/features.py` | Build only decision-time features; exclude future outcomes and ground-truth labels. |
| `ml/train.py`, `predict.py`, `evaluate.py`, `explain.py` | Train, score, measure, and explain models. |
| `core/graph.py` | Construct time-stamped wallet transfer graph and trace paths. |
| `core/taint.py` | Propagate a proportional estimate of potentially tainted value. |
| `core/intervention.py`, `policy.yaml` | Apply configurable business rules and produce an explainable bounded recommendation. |
| `core/simulator.py`, `baseline.py` | Replay scenarios and compare the recommendation strategy to direct-recipient-only baseline. |
| `backend/` | Expose analysis, incident, decision, simulation, metrics, and demo APIs; persist audit records. |
| `frontend/` | Present incidents, graph, evidence, taint, predictions, recommendation, analyst controls, and outcomes. |
| `docs/` | Maintain architecture, data dictionary, model card, responsible-AI, API, limitations, and demo materials. |

## Core records

- **Transaction:** a time-stamped transfer or cash-out event between synthetic wallets/agents.
- **Wallet:** synthetic account attributes and balances used to create baseline behavior.
- **Incident:** report metadata and a reference to a reported transaction.
- **Ground truth:** generator-only labels for evaluation; not available as model input at inference time.
- **Analysis result:** model scores, graph trace, taint estimates, predicted next move, recommendation, and evidence references.
- **Analyst decision:** approve/reject/modify action, reason, actor, timestamp, and simulated result.

## Important boundaries

- The fraud model may provide a score; policy code determines whether that score and other evidence meet recommendation criteria.
- The recommendation is not a legal finding and cannot execute a real wallet action.
- Ground truth and future transactions are used for evaluation only and must not leak into inference features.
- Graph edges and predictions should carry timestamps and a stated observation window.
- Every value-preserved metric must specify its scenario assumptions and compare identical scenario inputs across baseline and FlowFreeze.
- A synthetic cash-out is recorded as a terminal ledger event; its `cash_destination` is not a digitally reachable customer wallet.

## MVP runtime

Run locally with a FastAPI backend, React/Vite frontend, SQLite database, and pre-generated synthetic demo data. Docker Compose may wrap local services after the core workflow works. The demo should remain usable without access to upay systems or internet services.
