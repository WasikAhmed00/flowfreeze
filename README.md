## Project Overview

### Problem Addressed

Digital financial fraud can spread rapidly through multiple wallets and transactions, making manual investigation difficult and time-consuming. Fraud analysts often need to identify suspicious behavior, trace fund movement, estimate potential exposure, and determine appropriate intervention actions while minimizing impact on legitimate users.

### Proposed Solution

FlowFreeze is an AI-assisted fraud containment and fund-flow intelligence platform that combines:

* Fraud risk prediction
* Transaction graph analysis
* Fund-flow tracing
* Taint estimation
* Next-move prediction
* Analyst-reviewed intervention recommendations

The platform provides explainable evidence and decision-support tools to help investigators analyze suspicious incidents using synthetic data in a safe demonstration environment.

### Purpose

The project was developed as a prototype for the upay BD sponsored hackathon to demonstrate how AI can assist fraud investigation workflows while maintaining human oversight and responsible decision-making.

---

## Features

In addition to the functionality described throughout this README, FlowFreeze includes:

### AI-Assisted Fraud Risk Detection

* Machine learning based fraud risk scoring
* Decision-time feature engineering
* Explainable model outputs for analyst review

### Fund Flow Intelligence

* Multi-hop transaction tracing
* Downstream wallet discovery
* Transaction relationship visualization

### Taint Estimation

* Proportional attribution methodology
* Estimated exposure tracking
* Visibility constrained to incident analysis time

### Next-Move Prediction

Prediction of likely wallet behavior:

* Forward transfer
* Cash-out
* No movement

### Analyst Decision Support

* Intervention recommendations
* Policy-based evaluation
* Human-in-the-loop review process

### Incident Investigation Dashboard

* Incident management
* Fund-flow analysis
* Evaluation metrics
* Synthetic case replay

### Financial Exposure & Response-Delay Analysis (Synthetic)

The Evaluation page now includes generated-ledger estimates for reported suspicious value, potentially exposed value, value identified beyond the direct recipient, downstream wallets, cash-outs, and response-delay snapshots. The **Why Multi-Hop Matters** view uses the currently selected synthetic case and displays its actual generated trace paths. With seed 42, the default case `SCN-06-FANOUT-CASHOUT-0003` shows three chronologically ordered digital-wallet hops ending in a cash-out.

Create the local database and reproduce the aggregate JSON/CSV artifacts:

```bash
python -m data_generator.generate --seed 42
python -m core.impact_analysis
```

The command writes `ml/artifacts/impact_analysis.json` and `ml/artifacts/impact_analysis.csv`. `GET /api/metrics` serves the aggregate artifact; `GET /api/metrics/impact/{scenario_id}` calculates the selected case's direct-recipient comparison and 0/5/10/15/30/60-minute replay curve from transaction timestamps.

**Interpretation:** potentially exposed value means remaining proportional taint in digital wallets plus taint attributed to observed cash-outs. “Missed exposure” is the multi-hop amount identified minus the amount identified at the direct recipient, floored at zero. Gross transaction volume deduplicates transaction IDs, but funds moving in separate hops may appear again as transaction volume. Potentially legitimate value at risk is an explicitly labeled per-wallet policy-cap illustration. None of these quantities is actual financial loss, ownership, observed prevention, or upay BD operational performance; delay windows are hypothetical, not measured response times. See [`docs/END_TO_END_EVALUATION.md`](docs/END_TO_END_EVALUATION.md), [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md), and [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md).

---

## Technology Stack

### Programming Languages

* Python 3.11+
* JavaScript / TypeScript

### Backend

* FastAPI
* Uvicorn

### Frontend

* React
* Vite
* Tailwind CSS

### Machine Learning & Analytics

* scikit-learn
* pandas
* NumPy
* NetworkX
* joblib

### Database

* SQLite

### AI Components

* Fraud Risk Prediction Model
* Next-Move Prediction Model
* Explainability Pipeline
* Intervention Recommendation Engine

### Services & Deployment

* Render
* GitHub

---

## Requirements

### Software Requirements

#### Backend

* Python 3.11 or newer
* pip

#### Frontend

* Node.js 20+
* npm

---

## Environment Variables

### Backend Environment Variables

Create a `.env` file if required by your deployment environment.

| Variable           | Purpose                      | Example                        |
| ------------------ | ---------------------------- | ------------------------------ |
| APP_ENV            | Application environment      | development                    |
| DATABASE_URL       | Database connection string   | sqlite:///./data/flowfreeze.db |
| RANDOM_SEED        | Synthetic dataset seed       | 42                             |
| ENABLE_DEMO_WRITES | Enable demo write operations | false                          |
| DEMO_WRITE_KEY     | Demo authorization key       | YOUR_SECRET_KEY                |

### Frontend Environment Variables

Create `frontend/.env.local`:

```env
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
```

Use deployment-specific URLs when hosting remotely.

> Never commit real credentials, secrets, API keys, or production configuration values.

---

## Build Instructions

### Frontend Production Build

```bash
cd frontend
npm run build
```

### Render Deployment Build

```bash
pip install -r requirements.txt
bash scripts/render-build.sh
```

### Render Startup Command

```bash
bash scripts/render-start.sh
```

---

## Live Deployment URL



https://flowfreeze-web.onrender.com


## Testing Instructions

### Automated Testing

Run the backend test suite:

```bash
pytest -q
```

Run a specific test module:

```bash
pytest tests/test_fraud_model.py
```

Run all tests with detailed output:

```bash
pytest -v
```

### Manual Feature Verification

Judges can verify the implemented features by following these steps:

#### 1. Start the Backend

```bash
python -m uvicorn backend.main:app --reload
```

Verify that the API is accessible:

```text
http://127.0.0.1:8000/docs
```

#### 2. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

#### 3. Verify Fraud Risk Detection

* Open an incident from the Incident Dashboard.
* Review the generated fraud risk score.
* Check the AI explanation panel and contributing risk indicators.

#### 4. Verify Fund Flow Intelligence

* Select an incident.
* Open the Fund Flow Graph.
* Confirm that downstream wallet connections and transaction paths are visualized.

#### 5. Verify Taint Estimation

* Open the Taint Analysis section.
* Review the estimated affected value and exposure calculations.

#### 6. Verify Next-Move Prediction

* Open the prediction panel.
* Confirm that the system generates probabilities for:

  * Forward Transfer
  * Cash-Out
  * No Movement

#### 7. Verify Intervention Recommendations

* Review the recommended analyst action.
* Confirm that supporting evidence and reasoning are displayed.

#### 8. Verify What-If Lab

* Open the What-If Lab.
* Modify simulation parameters.
* Run a scenario.
* Compare the original and simulated outcomes.

#### 9. Verify Incident Replay

* Open a replayable incident.
* Run the replay.
* Confirm that historical events and decisions can be reviewed step-by-step.

### Expected Outcome

The platform should successfully demonstrate:

* AI-assisted fraud risk detection
* Fund-flow tracing
* Taint estimation
* Next-move prediction
* Intervention recommendation generation
* Incident replay and simulation capabilities
* Analyst-focused investigation workflows


## Additional Configuration

### Important Documentation

The following project documents provide additional configuration, methodology, and evaluation details:

* `docs/API.md`
* `docs/DATA_DICTIONARY.md`
* `docs/INTERVENTION_POLICY.md`
* `docs/MODEL_CARD.md`
* `docs/RESPONSIBLE_AI.md`
* `docs/LIMITATIONS.md`
* `docs/TAINT_METHODOLOGY.md`
* `docs/END_TO_END_EVALUATION.md`
* `docs/RENDER_FREE_TIER.md`

### Demo Notes

* Synthetic data only
* No production customer information
* No real fund freezing capability
* Human analyst review required for recommendations
* All intervention actions are simulated
