# FlowFreeze Prototype Limitations

## Data and evaluation

- All included records are generated. They do not represent upay BD, its customers, transaction patterns, or operating performance.
- Train, validation, and test contain variants of the same eight scenario templates. This is not a temporal, new-family, production, or adversarial evaluation.
- The classifier's perfect results on the held-out generated test cases demonstrate consistency with the generator's labels, not reliable fraud detection in an MFS environment.
- Taint is proportional attribution, an accounting assumption. It does not establish source, ownership, fraud, or legal recoverability.
- Step 9's “preserved” and “legitimate affected” values are counterfactual sums against generated remaining-taint labels. They assume an immediate proposal takes effect and are not measured loss prevention or customer impact.
- Local recommendation timing excludes process startup, initial feature generation, and model loading. It varies by computer.

## Operational limits

- There is no production authentication, access control, provider integration, wallet-control endpoint, or real-time event feed.
- The SQLite database and audit records are local prototype state. Demo reset replaces the database and clears that local audit history.
- Models are locally trained synthetic artifacts and are ignored by Git; a new checkout must train them before showing live model outputs.
- No formal fairness, subgroup, out-of-distribution, calibration-in-production, robustness, or security assessment has been completed.
- There is no incident case-management or customer appeal workflow.

## Before any real-world validation

Keep this project offline and synthetic until upay BD and appropriate legal, privacy, security, and regulatory owners authorize a separately governed evaluation. That effort would require representative and independently labeled data; clear purpose and retention limits; access controls; time-based and out-of-family testing; calibration and subgroup error analysis; threat and abuse testing; human review and appeal design; operational monitoring; and explicit approval for any provider integration. Passing this prototype's demo does not satisfy those requirements.
