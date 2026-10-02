# FlowFreeze frontend

React + Vite analyst workspace for the synthetic FlowFreeze API.

## Run locally

1. In the repository root, generate the database and start the API:

   ```powershell
   python -m data_generator.generate --seed 42
   python -m uvicorn backend.main:app --reload
   ```

2. In this `frontend/` directory, install from the committed lockfile and start Vite:

   ```powershell
   npm ci
   npm run dev
   ```

3. Open `http://127.0.0.1:5173`.

Set `VITE_API_BASE_URL` in `.env.local` to use a different local API address. A copyable example is in `.env.example`.

## Screens

- Overview: synthetic case inventory, dataset totals, audit counts, search, and paging.
- Incident detail: time-bounded graph and evidence, proportional taint estimates, wallet context, policy recommendation, analyst decision, and one-shot what-if outcome.
- Direct-recipient-only comparison: same-snapshot coverage comparison against the traced network, clearly separated from preserved-value outcomes.
- What-if lab: choose a generated scenario and examine it using the incident review flow.
- Evaluation: synthetic dataset and simulation estimates, with a clear notice that ML metrics are not available before roadmap Step 5.
- Audit trail: recorded analyst actions with actor, reason, amount, and timestamp.

The demo entry is a client-side prototype gate, not authentication. The API has no production authentication and must remain local. Optional score controls on incident detail are prominently labeled **illustrative only**. Leaving them disabled sends no model scores and therefore retains the policy's review-only behavior.
