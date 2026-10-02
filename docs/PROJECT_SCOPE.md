# FlowFreeze Project Scope

## Context

FlowFreeze is a prototype for the upay BD sponsored hackathon. It explores whether an analyst can use transaction-flow intelligence to find suspicious funds that move through multiple wallets before a report is investigated.

## Problem statement

When a customer reports a suspicious MFS transfer, looking only at the first recipient can miss potentially recoverable e-money that has moved to other wallets or cash-out points. Analysts need a quick way to review the reported transfer, follow downstream flows, understand the evidence and uncertainty, and prioritize a proportionate response.

## Primary user

**Fraud or trust-and-safety analyst** reviewing a reported transaction. The analyst needs to understand where funds moved, what amount may remain digitally reachable, why a wallet is considered risky, and what a proposed response could affect.

The prototype is not a customer-facing case filing product and does not assume access to upay production systems.

## Proposed solution

Given a synthetic incident, FlowFreeze will:

1. Load the reported transaction and its time context.
2. Score relevant transaction and wallet behavior.
3. Build a time-aware graph of linked transfers and cash-outs.
4. Estimate potentially tainted value per wallet using proportional attribution.
5. Predict likely next movement within a configurable time window.
6. Recommend a bounded simulated intervention with evidence, uncertainty, and potential legitimate-value impact.
7. Let an analyst approve, reject, or modify the simulated recommendation with a recorded reason.
8. Compare the simulated outcome to a direct-recipient-only baseline.

## System boundary and safeguards

- Inputs and outcomes are synthetic and generated for the demo.
- No real upay transaction, customer, NID, wallet, location, or credential data is used.
- The system does not connect to a live wallet system or perform a real hold, freeze, reversal, refund, or confiscation.
- Recommendations are decision support, not determinations of fraud or legal authority.
- A human analyst sees evidence and can reject or modify every recommendation.
- Model scores, policy rules, and analyst decisions are separate and auditable.
- Legal, operational, provider, and regulatory feasibility of any real intervention is out of scope and requires validation.

## MVP success measures

All measures below are computed on deterministic synthetic scenarios and must be labeled as simulated results.

| Measure | MVP definition |
|---|---|
| Potential value preserved | Synthetic value that remains digitally reachable under the simulated intervention at the decision time, compared with scenario ground truth. |
| Share of reported value preserved | Potential value preserved divided by reported amount. |
| Innocent value affected | Value included in a simulated intervention that ground truth marks legitimate. |
| Downstream wallets identified | Correct downstream wallet count relative to the generated scenario graph. |
| Recommendation time | Elapsed processing time from analysis request to recommendation response. |
| Fraud model quality | Precision, recall, F1, confusion matrix, and PR-AUC when class distribution supports it. |
| Next-move model quality | Per-class metrics and confusion matrix for forward, cash-out, and no movement within the prediction window. |

Primary competition outcome: compare potential value preserved and innocent value affected against a baseline that reviews only the direct recipient. Do not claim synthetic results represent upay performance.

## MVP scenarios

1. **Direct fraud:** victim to one recipient, with funds still there.
2. **Fan-out:** the first recipient splits funds across several wallets.
3. **Multi-hop layering:** funds move across sequential wallets.
4. **Mixed balance:** a downstream wallet holds both legitimate and potentially tainted value.
5. **Rapid cash-out:** funds move to an agent/cash-out event shortly after receipt.
6. **Fan-out plus cash-out:** one branch cashes out while another remains digital.
7. **False-positive near miss:** unusual but legitimate activity should not be treated as confirmed fraud.
8. **Wrong-recipient dispute:** authorized transfer reported as sent to the wrong recipient; handled as a distinct incident type.

The first end-to-end demo should use scenario 6 because it can show downstream tracing, an exited branch, a still-digital branch, taint estimation, a next-move prediction, and collateral-aware recommendation in one story. Other scenarios provide edge cases and evaluation coverage.

## Judge demo story

1. An example victim reports a synthetic ৳50,000 incident.
2. The analyst opens the incident and runs FlowFreeze.
3. The system finds the first recipient and draws time-ordered transfer paths.
4. One branch has cashed out; another has forwarded funds to a downstream wallet.
5. The system estimates remaining potentially tainted value and shows legitimate balance exposure separately.
6. It predicts likely next movement and explains the evidence and uncertainty.
7. It recommends a partial simulated intervention bounded by the estimated tainted amount.
8. The analyst reviews the evidence, approves/edits/rejects the simulation, and records a reason.
9. The evaluation view compares potential value preserved and innocent value affected against the direct-recipient-only baseline.

All amounts and outcomes in this story are generated demo values, not upay statistics.

## Decisions for the MVP

- **Database:** SQLite for local demo simplicity.
- **Data:** seeded, deterministic synthetic data; CSVs plus SQLite for the requested project layout.
- **Graph:** NetworkX backend representation; frontend graph visualization selected during UI implementation.
- **Taint:** proportional attribution is the primary MVP method.
- **Fraud baseline:** explicit rules and a simple scikit-learn model before attempting a more complex model.
- **Next move:** predict forward, cash-out, or no movement within a configurable five-minute window.
- **Intervention:** policy-based recommendation using model outputs as inputs; no model or LLM directly authorizes action.
- **Demo:** local/offline-first, resettable, and reproducible.

## Out of scope for the hackathon prototype

- Live upay system integration or real-time production monitoring.
- Processing real customer data or personally identifying information.
- Executing legal or operational wallet holds.
- Automatically deciding that a customer committed fraud.
- Claiming real-world fraud reduction, recovery, or customer impact from synthetic results.
- Using a language model as the authority for financial action.

## Open assumptions to confirm

- Whether the competition requires a specific submission date, deployment platform, or mandatory framework.
- Whether the team wants the demo amount and labels in Bangladeshi taka (৳); this draft assumes yes.
- Whether the team has a preferred visual direction or branding assets; none are assumed yet.
