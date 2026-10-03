# Step 9: End-to-End Synthetic Evaluation

## Reproduce

Generate the default deterministic demo data, train the models, then run the held-out experiment:

```powershell
python -m data_generator.generate --seed 42
python -m ml.train --seed 42
python -m core.baseline --split test
```

The command writes `ml/artifacts/end_to_end_metrics.json`; `GET /api/metrics` serves the results to the Evaluation page. Model artifacts are local and ignored by Git. The checked-in result JSON records one run so the demo is reviewable without local joblib files.

## Experiment design

- Both strategies use the same 120 held-out incident cases, decision-time model scores, proportional taint estimates, policy v1 thresholds, analysis snapshots, and per-wallet hold cap.
- **Direct-recipient-only** can propose only for the receiver of the reported transaction.
- **FlowFreeze network** can propose for any wallet with a positive proportional-taint estimate in the traced scenario.
- A recommendation remains a proposal requiring an analyst. For this offline what-if benchmark only, its amount is scored against the generator's `tainted_amount` remaining at `analysis_at`.
- “Estimated tainted value preserved” is `min(proposed amount, generated remaining taint)`. “Estimated legitimate value affected” is the excess proposal over that generated taint.
- Results assume a proposal takes effect immediately at `analysis_at`; no later transaction replay validates that assumption. These figures are not observed prevented losses or actual customer impact.
- Timing is local per-case model inference, replay, graph, taint, and policy time. It excludes Python process startup, initial feature-table construction, and model loading. It is machine-dependent.

## Recorded run

Seed 42, default policy v1, eleven generated families, test split (165 cases and 1,155 test wallet rows):

| Measure | Direct recipient only | FlowFreeze network | Difference |
|---|---:|---:|---:|
| Cases with a proposal | 30 (25.0%) | 75 (62.5%) | +45 cases |
| Proposed amount | ৳300,000.00 | ৳900,000.00 | +৳600,000.00 |
| Estimated tainted amount preserved | ৳299,955.17 | ৳815,302.41 | +৳515,347.24 |
| Estimated legitimate value affected | ৳44.83 | ৳84,697.59 | +৳84,652.76 |

Graph tracing reported an average 1.125 downstream wallets per incident (135 across these cases); the generated labels indicate 135 positive-taint downstream-wallet occurrences were found. The measured median per-case recommendation time was 33.8 ms and p95 was 48.699 ms on the run environment. Detailed per-family results are in `ml/artifacts/end_to_end_metrics.json`.

The extra proposed amount finds additional generated tainted value, and also adds substantial estimated legitimate collateral impact, especially in mixed-balance scenarios. The result illustrates a precision/collateral tradeoff under the generator assumptions; it does not establish that network-based intervention is better for real MFS customers. Step 5 model metrics are reported separately and share the limitations in `MODEL_CARD.md`.
