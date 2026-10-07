# FlowFreeze Business Impact Framework

> **SYNTHETIC BUSINESS SIMULATION — NOT PRODUCTION PERFORMANCE.** Every computed value comes from generated CSV transaction, incident and ground-truth records. Analyst timing is an explicit synthetic operational model. No value below is a claim of actual MFS fraud-loss reduction, customer-harm reduction or productivity improvement.

## Business value chain

FlowFreeze is intended to support the following hypothesis, which still requires validation:

**Earlier risk identification → faster investigation → better downstream tracing → more exposure identified → more proportionate intervention → less fraud loss → fewer unnecessary holds → less customer harm → better analyst productivity → business value.**

Each arrow is a hypothesis, not a guaranteed causal effect. Graph coverage does not by itself prove fraud; attributed exposure is not recoverable money; a recommendation does not execute a hold; and avoided customer harm must be measured, not inferred from a synthetic scenario.

## KPI framework

| Area | KPI | Current status / interpretation |
|---|---|---|
| Fraud loss | Estimated fraud exposure; simulated prevented exposure; exposure identified before/after cash-out; simulated loss-reduction rate | Calculated from generated incident/transaction/taint-label records. “Prevented” means simulated exposure under an immediate-intervention counterfactual, never actual prevented loss. |
| Investigation | Time to first useful signal; time to downstream wallets/exposure; handling time; transactions/wallets reviewed; investigation coverage | Signal and review counts derive from generated event timestamps/network. Handling-time comparison uses the declared synthetic/manual model below, not analyst trials. |
| Customer harm | Unnecessary holds; legitimate value affected; false-positive interventions; legitimate customers affected; proportionate intervention rate | Synthetic policy simulation only. Real customer outcomes are not in this dataset. |
| Operations | Cases/hour; time saved; downstream wallets/case; alerts prioritized; escalation rate | Cases/hour and time saved inherit the synthetic timing model. Escalation rate is unavailable and remains a future validation target. |
| NEXT-MOVE | Cash-out recall; forwarding recall; macro F1; calibration | Model evaluation artifacts are synthetic held-out diagnostics. They are not real operating KPIs; real-world calibration and recall require labeled pilot outcomes. |

## Counterfactual workflows

### Baseline

Direct-recipient-only investigation: inspect the recipient of the reported transaction and its directly available records; no FlowFreeze risk prioritization; no automated multihop discovery; intervention is limited to the directly identified recipient and synthetic policy amount.

### FlowFreeze-assisted

Use the generated observed transaction flow to discover downstream wallets (cycle-safe, at most five hops), use synthetic generated taint labels to quantify remaining linked exposure, and apply an observable evidence proxy (cash-out or multi-recipient behavior) for simulated prioritization. The prototype still requires an analyst decision; no wallet action is executed.

The script reports scenario-level records, aggregated baseline-vs-FlowFreeze comparisons, and direct/multihop comparisons by generated scenario family. **It is a counterfactual simulation over synthetic labels, not a controlled trial.**

## Formulas

- **Initial suspicious value:** incident `reported_amount` from the generated incident record.
- **Cash-out before/after investigation:** sum of generated cash-out transaction amounts after the reported time and respectively at/before `analysis_at`, or after `analysis_at`.
- **Potentially interceptable exposure:** `min(max(0, initial suspicious value − generated cash-out value before analysis), generated tainted_amount remaining at analysis)`. It is a labeled synthetic exposure proxy.
- **Potential exposure identified:** sum of generated `tainted_amount` labels for identified fraud wallets (direct recipient for baseline; reachable network for FlowFreeze). Gross edge values are not summed as distinct exposure, avoiding repeated counting as funds move through hops.
- **Simulated prevented exposure:** `min(potentially interceptable exposure, exposure identified by that workflow)`. This assumes immediate intervention at analysis. It is **not actual prevented loss**.
- **Simulated loss-reduction rate:** `sum(simulated prevented exposure) / sum(initial suspicious value)`. It is a synthetic scenario ratio; it does not establish actual loss reduction.
- **Investigation-time model:** per case, `4.0 minutes intake + 1.5 minutes × distinct transactions reviewed + 0.75 minutes × wallets reviewed`. Time saved is baseline modeled minutes minus FlowFreeze modeled minutes. The constants are transparent illustrative assumptions, not empirical timings; a negative result means the modeled FlowFreeze workflow takes longer.
- **Legitimate value affected / unnecessary holds:** the over-aggressive comparator holds the full reported amount in every synthetic legitimate case. The FlowFreeze proxy selects only reachable generated fraud wallets with observed cash-out/multirecipient evidence and bounds the proposed amount to identified taint. Therefore it has zero collateral by construction in this simplified experiment; this must not be interpreted as a real false-positive rate or proof that customer harm is avoided.
- **Unnecessary intervention rate:** simulated unnecessary interventions divided by synthetic legitimate cases; if no legitimate cases exist, the denominator is bounded to one and the value is zero.

## Running the simulation

From the repository root:

```bash
python -m core.business_impact
```

Writes `ml/artifacts/business_impact.json`, `ml/artifacts/business_impact.csv`, and `ml/artifacts/customer_harm_metrics.json`. The API also computes current results from the generated CSVs at `GET /api/metrics/business-impact` (the path is relative to the repository's existing `/api` prefix).

## Synthetic assumptions and limitations

- Inputs are generated synthetic transactions, incidents and generator labels only; no real MFS cases or customer data are present.
- The generated `tainted_amount` labels act as an outcome oracle for the remaining-exposure calculation. In real operations, taint is uncertain and does not establish fraud, ownership, or recoverability.
- The graph uses observed post-report movement through analysis time, bounded to five hops. It does not model a live feed, delayed data arrival, operational queue, or action latency.
- The manual investigation-time model is illustrative and may favor either workflow; replace it with timed analyst trials before making efficiency claims.
- The aggressive-hold and evidence-proxy policies are simplified synthetic comparisons, not production policies. The FlowFreeze proxy intentionally chooses taint-bounded amounts, so its modeled legitimate collateral can be zero by construction.
- These outputs are not causal estimates. Synthetic scenario-family frequency and generated labels are not representative evidence of real-world prevalence or performance.

### Evidence required before making actual-impact claims

**Actual fraud-loss reduction** requires authorized, representative real MFS fraud cases, independently confirmed outcomes, intervention timestamps, cash-out outcomes, analyst timing data, and a controlled comparison (for example, governed shadow mode followed by an appropriately reviewed pilot). **Actual customer-harm reduction** additionally requires real false-positive data, hold outcomes, and customer-impact measurement. Legal, privacy, security, regulatory and operational approval is required before using real data or integrating with a provider.

Until that evidence exists, real fraud-loss reduction, response-time improvement, and customer-harm reduction are **future validation targets**, not achieved benefits.
