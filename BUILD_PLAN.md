# FlowFreeze Build Plan

FlowFreeze is a hackathon prototype for **upay BD**, an MFS provider. It uses synthetic data to help an authorized analyst trace reported suspicious transfers, estimate potentially tainted e-money, predict likely next movement, and review proportionate intervention recommendations.

## Current status

Roadmap Steps 0–10 are implemented for a local, synthetic-data demonstration. The complete analyst flow, held-out ML evaluation, same-case direct-recipient comparison, Windows startup/reset guidance, judge walkthrough, and pitch deck are available in this repository. The Step 9 report's values are counterfactual synthetic estimates, and the models do not demonstrate real-world or upay BD performance. See `docs/END_TO_END_EVALUATION.md`, `docs/LIMITATIONS.md`, and `demo/DEMO_SCRIPT.md`.

## Product boundary

This prototype does not autonomously confiscate, reverse, refund, or legally freeze customer money. Recommendations are for analyst review and simulation only. Any real hold capability would need provider, legal, and regulatory validation. Use synthetic data only; never commit real customer data, credentials, or wallet identifiers.

## Build sequence

### 0. Agree the scope and demo story

- Confirm the analyst persona and the incident-to-outcome journey.
- Define synthetic-only scope, assumptions, and what the prototype cannot do.
- Choose success measures: value preserved before cash-out, innocent value affected, recommendation time, tracing accuracy, and model metrics.
- Finalize demo scenarios, including direct fraud, fan-out, multi-hop layering, rapid cash-out, mixed funds, a false positive, and a wrong-recipient dispute.
- Record the architecture and data schema before building screens.

**Deliverables:** `docs/ARCHITECTURE.md`, `docs/DATA_DICTIONARY.md`, scenario definitions, and a measurable demo plan.

### 1. Set up the project and safe data workflow

- Establish the requested `flowfreeze/` directory layout.
- Define reproducible environment setup, configuration, and database initialization.
- Add synthetic data generation with a fixed seed and clear scenario ground truth.
- Add a data dictionary and keep generated data clearly labeled as synthetic.

**Deliverables:** `data_generator/`, synthetic CSV/database outputs, `requirements.txt`, `.env.example`, and local run instructions.

### 2. Build the transaction and replay engine

- Load transactions, wallets, and incidents into SQLite for the MVP.
- Validate required fields, timestamps, amounts, and wallet references.
- Track wallet balances and cash-out events.
- Support deterministic time-ordered scenario replay and demo reset.

**Deliverables:** working data ingestion and replayable transaction history.

### 3. Build the transaction graph and fund tracing

- Represent wallets as nodes and transfers as time-stamped edges.
- Trace downstream paths by hop count and time window.
- Identify fan-out, rapid forwarding, and cash-out edges.
- Return evidence and limits with each traced path.

**Deliverables:** `core/graph.py` and a trace result usable by the API and graph view.

### 4. Build the taint attribution engine

- Implement proportional attribution as the explainable MVP method.
- Track tainted value through transfers without exceeding available balances.
- Report potentially tainted and potentially legitimate value separately.
- Optionally compare whole-balance, first-out, and last-out assumptions.

**Deliverables:** `core/taint.py` and scenario-level collateral-impact measurements.

### 5. Build fraud scoring and next-move prediction

- Establish a transparent rules/logistic-regression baseline.
- Create leakage-safe features from information available at decision time.
- Train and compare a tree-based fraud model if the synthetic data supports it.
- Define the next-move target (for example, forward, cash out, or no movement within five minutes).
- Evaluate with precision, recall, F1, confusion matrix, and PR-AUC where suitable.
- Save model artifacts and document confidence, limits, and evaluation split.

**Deliverables:** `ml/` training, inference, explanation, and evaluation code plus documented model metrics.

### 6. Build proportionate recommendations and explanations

- Combine risk, tainted amount, available balance, predicted movement, cash-out probability, and collateral exposure.
- Keep model predictions separate from configurable policy rules.
- Recommend a bounded simulated intervention; never auto-approve it.
- Explain why the wallet, amount, and action were recommended, with uncertainty and evidence.

**Deliverables:** `core/intervention.py`, `core/policy.yaml`, and an evidence-backed recommendation.

### 7. Build the backend and audit workflow

- Create FastAPI endpoints for incidents, analysis, decisions, simulation, metrics, and demo reset.
- Keep graph, taint, ML, and policy logic in their own modules.
- Record analyst approve/reject/modify decisions, reasons, timestamps, and simulated outcomes.
- Validate inputs and provide a seeded demo case.

**Deliverables:** usable API, SQLite persistence, and an audit trail.

### 8. Build the analyst frontend

- Implement dashboard and incident list/detail views.
- Show the transaction graph, wallet facts, risk evidence, taint estimates, and next-move probabilities.
- Present the recommendation and its rationale before approval controls.
- Add what-if simulation, baseline comparison, evaluation, and audit history.

**Deliverables:** working analyst flow from opening an incident through reviewing and recording a decision.

### 9. Integrate and evaluate end to end

- Connect incident intake through risk, graph, tracing, taint, prediction, recommendation, analyst decision, and outcome.
- Compare FlowFreeze against the direct-recipient-only baseline on the same deterministic scenarios.
- Report value preserved, innocent value affected, time to recommendation, downstream wallets found, and ML performance.
- Do not describe synthetic results as upay production statistics.

**Deliverables:** reproducible experiment, evaluation dashboard, and measured demo results.

### 10. Prepare the hackathon demo and handoff

- Make the app start locally with clear instructions; add Docker support if time permits.
- Seed and reset the demo scenario reliably and prepare a backup recording/screenshots.
- Complete the README, architecture, model card, responsible AI, limitations, data dictionary, API notes, and demo script.
- Prepare the pitch: problem, AI role, user journey, measured impact, safeguards, and path to validation.

**Deliverables:** a stable offline-capable demo and judge-ready evidence.

## Suggested checkpoints

1. **Foundation:** scope, synthetic generator, database, and demo data.
2. **Intelligence:** graph, tracing, taint, baseline, and ML evaluation.
3. **Action:** recommendation policy, explanations, decisions, and audit.
4. **Product:** frontend workflow and end-to-end integration.
5. **Evidence:** baseline experiment, responsible-AI documentation, and pitch demo.

## Definition of done

A seeded synthetic incident can be opened, analyzed, traced across wallets, assigned a taint estimate and next-move prediction, and given an explainable proportionate recommendation. An analyst can approve, reject, or modify it; the app simulates the outcome, records the decision, and compares value preserved and innocent value affected against the direct-recipient baseline. The demo is repeatable, documented, and contains no real customer or production data.

## Mapping to the requested repository structure

The requested `data_generator/`, `ml/`, `core/`, `backend/`, `frontend/`, `tests/`, `docs/`, and `demo/` folders cover the roadmap. Additional documentation such as a data dictionary, model card, responsible-AI statement, API notes, limitations, and project report can live under `docs/` as the project matures. Start with SQLite and synthetic CSV files; consider a larger database only if the prototype needs it.
