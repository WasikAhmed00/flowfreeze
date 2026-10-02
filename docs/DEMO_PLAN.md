# FlowFreeze Judge Demo Plan

## Objective

Show how an analyst can use FlowFreeze to trace a synthetic reported transfer, distinguish funds that have left digitally from funds that may remain reachable, review a bounded recommendation, and compare it with a direct-recipient-only baseline.

## Primary scenario

Use a deterministic fan-out plus cash-out case. Example story values are placeholders for generated data and must not be described as upay statistics:

```text
Victim reports a synthetic ৳50,000 transfer
                    ↓
                   W1
             ┌──────┴──────┐
             ↓             ↓
       Agent/cash-out      W3
                           ↓
                           W4
```

The generator must determine the actual balances, transfers, and ground truth. Keep one branch cashed out and at least one branch with funds still digital so the trace and recommendation have something meaningful to compare.

## Analyst walkthrough

1. Open the pre-seeded incident from the dashboard.
2. Run analysis and show the reported transfer, risk factors, and analysis timestamp.
3. Follow the graph from the direct recipient to downstream wallets and cash-out events.
4. Select a wallet and inspect balance, inflow/outflow, risk evidence, and estimated tainted versus legitimate value.
5. Review next-move probabilities and their prediction window.
6. Review the intervention amount, policy rationale, uncertainty, and potential innocent-value impact.
7. Approve, modify, or reject the simulation and enter a reason.
8. Open evaluation and compare FlowFreeze with direct-recipient-only baseline on the same generated case.
9. Reset and replay the scenario to demonstrate repeatability.

## Evidence shown to judges

- Downstream wallets correctly identified against scenario ground truth.
- Potentially tainted value estimated versus legitimate value affected.
- Prediction output and its evaluation quality.
- Time from analysis request to recommendation.
- Simulated value preserved and collateral impact relative to the baseline.
- Audit record of the analyst's decision.

## Demo readiness checklist

- [x] Seeded scenario is repeatable; the live `SCN-06-FANOUT-CASHOUT-0001` case was opened during Step 10 verification.
- [x] Generated data and figures carry synthetic-data labels.
- [x] `python -m demo.reset_demo --seed 42` restores the seeded CSV/database state and clears local audit history.
- [x] The app starts locally without upay connectivity or production credentials using `demo/start_demo.ps1`.
- [x] The API, frontend, trained model outputs, graph, taint, and recommendation loaded end to end.
- [x] Evidence appears before analyst decision controls.
- [x] Approve, modify, and reject controls are available; each records a local analyst decision and simulated outcome only.
- [x] The six-slide pitch deck is in `demo/pitch_deck.pptx`; a live synthetic incident screenshot was captured in the Codex task thread as backup visual evidence.
- [x] The [demo script](demo/DEMO_SCRIPT.md) distinguishes model prediction, policy recommendation, and analyst decision.

The Windows startup script and production deck were verified in this task. No Docker setup or MP4 recording is included; the app is intended to run locally after dependencies are installed, and the deck plus captured incident view provide the backup presentation material.
