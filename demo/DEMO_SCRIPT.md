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

## Six-minute business-operations walkthrough

### 0:00–0:40 — Set the boundary

**Say:** “For MFS fraud and risk operations, FlowFreeze is an AI fund-flow investigation and decision-support platform. It helps analysts detect, trace, quantify, predict, and prioritize suspicious money movement. It is an intelligence layer, not the transaction engine; today this is synthetic-only and cannot execute a hold.”

Show the Overview page and the synthetic data labels.

### 0:40–1:30 — Show queue priority and open a case

Show the analyst queue and the business-output-to-decision mapping, then open `SCN-06-FANOUT-CASHOUT-0001` from the incident list. Explain that attention bands must be partner-governed and are not automatic action thresholds.

**Say:** “This case has a reported transfer and a defined analysis timestamp. We only use transactions visible by that time. The IDs and values are generated for this demonstration.”

### 1:30–2:30 — Read the operational case file and follow the flow

Read the operational summary: what happened, why it may be risky, money potentially at risk, where it moved, next-move availability, recommended response, decision owner, urgency/SLA status, and audit state. Point out the graph, downstream wallets, cash-out evidence, and proportional taint table. Select one wallet and show its balance and transaction facts.

**Say:** “Edges show observed gross transfers. Taint is a separate proportional bookkeeping estimate; it is not a legal ownership or fraud finding.”

### 2:30–3:20 — Explain the model and policy

Show synthetic fraud risk and next-move scores, then the recommendation evidence, cap, and legitimate-value estimate.

**Say:** “The model output is advisory and trained on generated patterns. The policy is a separate layer. An analyst still has to review the evidence and record a decision.”

### 3:20–4:20 — Make and audit a human decision

Use a demo reason and reject or modify a proposal. If you record an approval/modification, keep the amount within the displayed bound. Run the one-time simulated outcome and open Audit Log.

**Say:** “This records a local decision and a synthetic what-if estimate. It does not change a wallet balance.”

### 4:20–5:30 — Separate synthetic business KPIs from validation

Open Evaluation. Show the same-case comparison and held-out model metrics. Call out the added estimated tainted value and the added estimated legitimate value affected, rather than presenting only the positive side.

**Say:** “Across 120 same-family synthetic test cases, the network strategy estimated ৳515,347 more tainted value preserved and ৳84,653 more legitimate value affected than the direct-recipient-only baseline. These are counterfactuals that assume immediate action, not observed outcomes. The classifier’s perfect scores reflect a small test split drawn from the same eight scenario templates; they are not upay performance.”

### 5:30–6:00 — Customer protection and validation path

**Say:** “Don't freeze everything. Investigate first when appropriate, and compare aggressive intervention with evidence-based, policy-governed responses. Legitimate cases affected, unnecessary holds, legitimate value affected, and proportionate interventions need real measured outcomes. Before real-world evaluation, obtain provider authorization, privacy/legal/security review, independently labeled representative cases, analyst trials and read-only shadow mode. This demo is synthetic only; no real benefit is claimed.”

## If the live demo fails

- Try the seeded data reset command above, then restart both services.
- Check `demo/.runtime/api.stderr.log` and `demo/.runtime/frontend.stderr.log` for startup errors.
- Use the pitch deck at `demo/pitch_deck.pptx` and the checked-in Step 9 metrics JSON to explain the workflow and benchmark, retaining every synthetic-data caveat.
- Do not substitute made-up or production-looking figures for missing live outputs.

## Business message and judge alignment

**Close with:** “FlowFreeze helps an MFS fraud operation decide faster, investigate deeper, and intervene more proportionately.” This is the product hypothesis, not a measured result.

- **Problem relevance:** places multi-hop fund-flow investigation after existing transaction-monitoring alerts in an MFS operations workflow.
- **Business/customer impact:** exposes case-level potential financial exposure and synthetic counterfactuals, while tracking investigation effort and customer-harm KPIs separately; no actual improvement is claimed.
- **AI depth:** connects risk scoring/explanations, graph tracing, taint estimation, next-move prediction, recommendations, and feedback/audit to analyst decisions.
- **Prototype:** walks through alert, prioritization, evidence, human decision, simulated impact, and audit.
- **Innovation:** combines behavioral intelligence and multi-hop funds tracing rather than stopping at transaction-level alerting.
- **Scalability:** identifies a proposed read-only, pseudonymous, versioned shadow architecture and phased validation gates; integration is future work.
- **Responsible AI:** no automatic financial action, uncertainty and synthetic-data labels, proportionality/customer-protection goals, audit, partner approval, and stop criteria.

For Judge 1, explicitly call out that fraud-loss reduction, response-time improvement, and harm avoided require real authorized analyst trials and outcome measurement. Judge 2's requested shadow-mode/pilot is addressed as a proposed staged validation plan, not an existing deployment. Judge 3's business alignment is addressed by actor roles, workflow placement, business KPIs, and the output-to-decision map.
