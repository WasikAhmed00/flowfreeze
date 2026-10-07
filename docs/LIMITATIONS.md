# FlowFreeze Prototype Limitations

## Data and evaluation

- All included records are generated. They do not represent upay BD, its customers, transaction patterns, or operating performance.
- Train, validation, and test contain variants of the same eleven scenario families. This is not a temporal, new-family, production, or adversarial evaluation.
- The classifier's perfect results on the held-out generated test cases demonstrate consistency with the generator's labels, not reliable fraud detection in an MFS environment.
- Taint is proportional attribution, an accounting assumption. It does not establish source, ownership, fraud, or legal recoverability.
- The end-to-end comparison's “estimated tainted value preserved” and “estimated legitimate value affected” values are counterfactual sums against generated remaining-taint labels. They assume an immediate proposal takes effect and are not measured loss prevention or customer impact.
- Local recommendation timing excludes process startup, initial feature generation, and model loading. It varies by computer.

## Financial exposure and response-delay analysis

- `python -m core.impact_analysis` compares a direct-recipient-only trace with the existing multi-hop trace on generated ledger events. “Missed exposure” means the additional proportional taint identified by the wider trace, not actual loss that a direct-only investigation would necessarily miss.
- Potentially exposed value is remaining taint in digital wallets plus taint attributed to observed cash-outs. It is an estimate under the proportional-flow assumption, not ground-truth loss, ownership, recoverability, or proof of fraud. Reported amount, currently remaining value, and already-cashed-out estimated value are separate measures.
- Delay points (0/5/10/15/30/60 minutes) replay generated transactions at `reported_at + delay`. They are illustrative windows, not measured response times, expected time-to-investigate, or evidence of how quickly funds would become unavailable in a real MFS system.
- Unique transaction IDs prevent repeated graph-path events from being counted twice. Gross values of different hop transactions may still represent the same underlying funds; transaction volume is not unique value.
- The potentially legitimate value at risk is a cap-based hypothetical applied to identified wallets, not an actual recommended or executed intervention. No simulated amount is described as observed prevented exposure.
- Validating financial impact requires institution-authorized representative transactions, verified outcomes and cash-outs, real report and action timestamps, independently reviewed labels, privacy/security/legal approval, and time-based and subgroup evaluation. None of those real-world data are present here.

## Operational limits

- There is no production authentication, access control, provider integration, wallet-control endpoint, or real-time event feed.
- The SQLite database and audit records are local prototype state. Demo reset replaces the database and clears that local audit history.
- Models are locally trained synthetic artifacts and are ignored by Git; a new checkout must train them before showing live model outputs.
- No formal fairness, subgroup, out-of-distribution, calibration-in-production, robustness, or security assessment has been completed.
- There is no incident case-management or customer appeal workflow.

## Before any real-world validation

Keep this project offline and synthetic until upay BD and appropriate legal, privacy, security, and regulatory owners authorize a separately governed evaluation. That effort would require representative and independently labeled data; clear purpose and retention limits; access controls; time-based and out-of-family testing; calibration and subgroup error analysis; threat and abuse testing; human review and appeal design; operational monitoring; and explicit approval for any provider integration. Passing this prototype's demo does not satisfy those requirements.
