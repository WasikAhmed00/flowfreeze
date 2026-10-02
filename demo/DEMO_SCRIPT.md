# FlowFreeze Hackathon Demo Script

## Before the demo

Use generated data only. Start from the repository root:

```powershell
.\demo\start_demo.ps1
```

Open `http://127.0.0.1:5173`. The API and frontend run locally; no upay system, credentials, or customer data are used. If you need a clean repeat, reset in another terminal:

```powershell
.\.venv\Scripts\python.exe -m demo.reset_demo --seed 42
```

Reset replaces the local generated SQLite database and clears its analyst audit history. Start/restart the API after reset so the screen refreshes cleanly. Stop both services with `.demostop_demo.ps1`.

## Six-minute walkthrough

### 0:00–0:40 — Set the boundary

**Say:** “FlowFreeze is a synthetic-data MFS incident-review prototype. It helps an analyst inspect where reported funds moved and compare a policy proposal with a direct-recipient-only view. It does not connect to upay accounts or execute a hold.”

Show the Overview page and the synthetic data labels.

### 0:40–1:30 — Open a seeded case

Open `SCN-06-FANOUT-CASHOUT-0001` from the incident list.

**Say:** “This case has a reported transfer and a defined analysis timestamp. We only use transactions visible by that time. The IDs and values are generated for this demonstration.”

### 1:30–2:30 — Follow the flow and attribution

Point out the graph, downstream wallets, cash-out evidence, and proportional taint table. Select one wallet and show its balance and transaction facts.

**Say:** “Edges show observed gross transfers. Taint is a separate proportional bookkeeping estimate; it is not a legal ownership or fraud finding.”

### 2:30–3:20 — Explain the model and policy

Show synthetic fraud risk and next-move scores, then the recommendation evidence, cap, and legitimate-value estimate.

**Say:** “The model output is advisory and trained on generated patterns. The policy is a separate layer. An analyst still has to review the evidence and record a decision.”

### 3:20–4:20 — Record a decision

Use a demo reason and reject or modify a proposal. If you record an approval/modification, keep the amount within the displayed bound. Run the one-time simulated outcome and open Audit Log.

**Say:** “This records a local decision and a synthetic what-if estimate. It does not change a wallet balance.”

### 4:20–5:30 — Show evaluation

Open Evaluation. Show the same-case comparison and held-out model metrics. Call out the added estimated tainted value and the added estimated legitimate value affected, rather than presenting only the positive side.

**Say:** “Across 120 same-family synthetic test cases, the network strategy estimated ৳515,347 more tainted value preserved and ৳84,653 more legitimate value affected than the direct-recipient-only baseline. These are counterfactuals that assume immediate action, not observed outcomes. The classifier’s perfect scores reflect a small test split drawn from the same eight scenario templates; they are not upay performance.”

### 5:30–6:00 — Reset and validation path

**Say:** “Before any real-world evaluation, this would need provider authorization, privacy and legal review, independently labeled representative data, out-of-time testing, subgroup and calibration analysis, and operational safeguards. This demo is synthetic only.”

## If the live demo fails

- Try the seeded data reset command above, then restart both services.
- Check `demo/.runtime/api.stderr.log` and `demo/.runtime/frontend.stderr.log` for startup errors.
- Use the pitch deck at `demo/pitch_deck.pptx` and the checked-in Step 9 metrics JSON to explain the workflow and benchmark, retaining every synthetic-data caveat.
- Do not substitute made-up or production-looking figures for missing live outputs.
