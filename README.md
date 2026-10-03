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

### Recommended Hardware

* 4 GB RAM minimum
* 8 GB RAM recommended
* Multi-core CPU recommended for model training

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
VITE_API_BASE_URL=http://127.0.0.1:8000
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

### Frontend

Replace with actual deployment URL:

```text
https://YOUR_FRONTEND_DEPLOYMENT_URL
```

### Backend

Replace with actual deployment URL:

```text
https://YOUR_BACKEND_DEPLOYMENT_URL
```

---

## Manual Verification Steps

Judges can verify the implemented features by following these steps:

1. Generate synthetic data.
2. Train the models.
3. Start the backend API.
4. Launch the frontend dashboard.
5. Open an incident.
6. Review fraud risk predictions.
7. Inspect downstream fund-flow tracing.
8. Review taint estimation results.
9. Generate intervention recommendations.
10. Execute scenario replay and evaluation workflows.

---

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
