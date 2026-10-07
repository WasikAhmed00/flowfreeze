# End-to-End Synthetic Evaluation

## Reproduce

Generate the deterministic synthetic database, train models if desired, run the held-out intervention experiment, and calculate transaction-timeline exposure diagnostics:

```bash
python -m data_generator.generate --seed 42
python -m ml.train --seed 42
python -m core.baseline --split test
python -m core.impact_analysis
```

The baseline command writes `ml/artifacts/end_to_end_metrics.json`. The impact command writes `ml/artifacts/impact_analysis.json` and a per-case/delay `ml/artifacts/impact_analysis.csv`. The checked-in JSON artifacts make the demo reviewable without local model files. `GET /api/metrics` serves aggregate metrics and `GET /api/metrics/impact/{scenario_id}` calculates a selected scenario's actual generated trace and response-delay curve.

## Held-out intervention comparison

The checked-in `end_to_end_metrics.json` describes 165 held-out synthetic cases from eleven generated scenario families. Both strategies use the same cases, decision-time model scores, taint estimates, policy thresholds, analysis snapshots, and per-wallet hold caps.

- **Direct-recipient-only** can propose only for the receiver of the reported transaction.
- **FlowFreeze network** can consider positively attributed wallets reachable in the traced scenario.
- “Estimated tainted value preserved” is `min(proposed amount, generator's remaining tainted_amount label at analysis_at)`.
- “Estimated legitimate value affected” is the excess proposal over that generated taint.
- This offline counterfactual assumes an immediate proposal at `analysis_at`; it is not observed loss prevention or customer impact.

| Measure | Direct recipient only | FlowFreeze network | Difference |
|---|---:|---:|---:|
| Cases with a proposal | 52 / 165 (31.52%) | 86 / 165 (52.12%) | +34 cases |
| Wallets with proposals | 52 | 103 | +51 |
| Proposed simulated amount | ৳519,823.00 | ৳1,007,488.00 | +৳487,665.00 |
| Estimated tainted value preserved | ৳519,774.39 | ৳987,379.25 | +৳467,604.86 |
| Estimated legitimate value affected | ৳48.61 | ৳20,108.75 | +৳20,060.14 |

Tracing found 131 downstream-wallet occurrences across those cases, 119 of which were labeled tainted by the generator. Median per-case recommendation time was 61.826 ms and p95 was 77.553 ms in the recorded run. These figures are run-specific local/synthetic metrics, not provider, customer, or production measurements. Detailed scenario-family results remain in `ml/artifacts/end_to_end_metrics.json`.

## Financial exposure analysis: definitions

The separate `impact_analysis.json` evaluates each generated incident at its `analysis_at` timestamp. It does not rely on model classifications or generator fraud labels to identify attributed value; it reuses the event-time simulator, graph tracer, and proportional-taint implementation.

For an incident snapshot:

- **Reported suspicious amount**: the reported incident amount attached to its referenced transaction.
- **Potentially tainted value remaining**: sum of proportional taint in current digital-wallet balances.
- **Potentially tainted value already cashed out**: sum of proportional taint assigned to observed cash-out events after the reported transaction.
- **Total potentially exposed value**: remaining estimated taint + estimated taint attributed to observed cash-outs. Unattributed value is reported separately; neither this total nor any component is ground-truth loss.
- **Direct-recipient exposure**: estimated taint remaining at the reported transaction's direct recipient plus taint attributed to that recipient's observed cash-outs within the shared trace window.
- **Multi-hop exposure**: estimated taint remaining in the direct recipient and downstream wallets reachable within the same 30-minute graph window and hop limit, plus trace-linked cash-out taint from those wallets.
- **Missed exposure**: `max(0, multi-hop exposure - direct-recipient exposure)`.
- **Exposure recovery rate**: `multi-hop exposure / total potentially exposed value`; it is zero when the denominator is zero. This is an estimated tracing-coverage ratio, not a recovery or prevention rate.
- **Unique transaction value examined**: sum of gross amounts for unique transaction IDs in the strategy's scope. Repeated transfers can represent the same underlying value; this is transaction volume, not unique economic funds.
- **Potentially legitimate value at risk**: an illustrative scenario that applies `min(current wallet balance, configured per-wallet policy cap)` to every identified wallet and subtracts estimated taint. It is neither a recommendation nor an executed hold.

Both strategies share the same incident snapshot, 30-minute trace window, hop limit, and taint method. Transaction IDs are deduplicated before strategy transaction volume is summed. A cash-out is counted once by transaction ID and its potentially tainted portion comes from `core/taint.py` attribution.

In the API and artifact, **downstream hops identified** counts unique reachable non-cash-out transaction edges. **Maximum downstream depth** counts transfer hops to the furthest identified digital wallet; terminal cash-out destinations are excluded from wallet depth and are counted separately as cash-out events.

## Response-delay analysis

The default delay windows are **0, 5, 10, 15, 30, and 60 minutes** after the generated `reported_at`. For each point the simulator reruns the scenario with `as_of = reported_at + delay`, so only events timestamped at or before that cutoff are visible. The graph trace uses a maximum 60-minute window, bounded by the replay cutoff. The selected-case API returns cumulative downstream transaction volume, wallets/depth, cash-outs before the hypothetical intervention, remaining taint, already-cashed-out taint, and their total. Aggregate results sum case-level values and also report per-case averages.

The Evaluation chart shows the selected case's **remaining-vs-cashed-out taint partition** and gross downstream transaction volume over those observed synthetic event times. The gross-volume series is transaction activity, not uniquely recoverable funds. The visualization is not an empirical response-time curve, measured operational delay distribution, or observed loss-prevention curve. No arbitrary percentage multiplier is used.

### Recorded impact-analysis run

The checked-in seed-42 `impact_analysis.json` contains 1,100 generated incidents evaluated at each case's `analysis_at` snapshot. Values below sum across independent synthetic cases; they are not an estimate of any institution's losses.

| Measure | Generated-data result |
|---|---:|
| Reported suspicious amount | ৳35,362,554.00 |
| Total potentially exposed value (remaining + attributed cash-outs) | ৳35,362,554.00 |
| Estimated taint remaining in wallets | ৳34,365,467.36 |
| Estimated taint already cashed out | ৳997,086.64 |
| Direct-recipient-only exposure identified | ৳25,218,633.77 |
| Multi-hop exposure identified | ৳33,801,526.85 |
| Incremental exposure identified beyond direct recipient | ৳8,582,893.08 |
| Downstream-wallet occurrences / traced cash-out events | 889 / 81 |

Delay outputs aggregate the exact timestamp-bounded ledger replays. Gross downstream transaction value is average per scenario; cash-out count is summed over the 1,100 scenarios.

| Delay after report | Avg. gross downstream transaction value | Avg. taint remaining | Avg. taint cashed out | Avg. downstream wallets | Avg. max digital depth | Cash-out events across cases |
|---:|---:|---:|---:|---:|---:|---:|
| 0 min | ৳0.00 | ৳32,147.77 | ৳0.00 | 0.0000 | 0.0000 | 0 |
| 5 min | ৳14,805.94 | ৳30,370.43 | ৳1,777.34 | 0.9527 | 0.7400 | 142 |
| 10 min | ৳17,355.33 | ৳29,572.34 | ৳2,575.42 | 1.1373 | 0.9245 | 214 |
| 15 min | ৳17,685.98 | ৳29,511.52 | ৳2,636.25 | 1.1645 | 0.9518 | 231 |
| 30 min | ৳18,423.96 | ৳29,511.52 | ৳2,636.25 | 1.2427 | 1.0300 | 231 |
| 60 min | ৳18,782.68 | ৳29,511.52 | ৳2,636.25 | 1.2936 | 1.0809 | 231 |

### Example selected-case replay

For generated case `SCN-06-FANOUT-CASHOUT-0003`, the reported suspicious amount is ৳50,438.00. At the 60-minute cutoff the actual traced path is `W1 → W2 → W3 → W4 → cash-out`, comprising three downstream digital-wallet hops and a terminal cash-out. The replay identifies three downstream wallets and two cash-out events. Direct-recipient-only identifies ৳34,595.92 of potentially tainted value; multi-hop identifies ৳50,438.00, an incremental ৳15,842.08. At this cutoff, ৳35,511.04 remains attributed to digital wallets and ৳14,926.96 is attributed to cash-outs. On the illustrated path, gross event amounts are ৳15,925, ৳14,996, ৳7,145, and ৳4,308; proportional-taint attribution for those events is ৳15,842.08, ৳14,531.92, ৳6,446.30, and ৳3,778.32. All figures come from that generated case's timestamped ledger, are estimates rather than actual loss, and do not imply prevented funds.

## Scope and validation needed

All numbers are generated synthetic estimates. Proportional taint is an accounting assumption, not a finding of fraud, fund ownership, legal recoverability, or actual financial loss. A hypothetical delay is not an estimate of upay BD's actual investigation time. A proposal is not evidence that funds would have been frozen or that a loss was prevented.

External evidence / validation needed: use only data and operational timelines authorized by the institution and independently reviewed for outcome quality. A real-world evaluation would require representative event and report timestamps; verified cash-out/return/recovery outcomes; documented investigation start, decision, and action times; privacy, security, legal, and regulatory review; time-based/out-of-family evaluation; subgroup error analysis; and a separately governed human-oversight and appeal workflow. Until then, do not interpret these results as upay BD production performance.
