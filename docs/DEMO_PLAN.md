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

- [ ] Scenario is seeded and repeatable.
- [ ] Generated data and all figures are labeled synthetic.
- [ ] Reset returns the app to a known clean state.
- [ ] The app works locally without production credentials or upay connectivity.
- [ ] Analysis completes end to end without manual code execution between screens.
- [ ] Evidence is visible before approval controls.
- [ ] Rejection and modification paths are demonstrable, not only approval.
- [ ] A backup recording or screenshots are available.
- [ ] The presenter distinguishes model prediction, policy recommendation, and analyst decision.
