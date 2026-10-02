# Simulated Intervention Policy

## Scope

`core/intervention.py` combines proportional taint estimates, observed graph evidence, and optional fraud-risk/next-move scores to produce an analyst-facing proposal. It does not execute wallet actions, call upay services, or change balances. The JSON-formatted `core/policy.yaml` is valid YAML 1.2 and is parsed using Python's standard library.

## Current defaults

| Setting | Default | Effect |
|---|---:|---|
| Minimum fraud-risk score | 0.65 | Required before a simulated hold can be proposed. |
| Minimum probability of forward or cashout movement | 0.55 | Required unless a cash-out is already observed. |
| Urgent review cash-out probability | 0.45 | Raises review urgency; it does not authorize an action. |
| Minimum potentially tainted estimate | ৳1,000 | Smaller estimates receive monitoring/review only. |
| Maximum simulated hold | ৳10,000 | Caps each proposal; it is also capped by the wallet's current replay balance. |

When a proposal exceeds its potentially tainted estimate, the result reports the estimated legitimate value that could be affected. Scores absent at inference time are explicitly unavailable; the policy does not invent them. Wrong-recipient disputes are routed for review without a simulated hold proposal.

## Output and evidence

Each wallet proposal includes its replay balance, potentially tainted and potentially legitimate estimates, score inputs, urgency, action, explanatory reasons, and transaction IDs from taint movements, rapid-forwarding/fan-out evidence, and observed cash-outs. The result identifies its `as_of` time, policy version, and limitations. Every result sets `requires_analyst_review` to true and `automatic_execution` to false.

## Limits

- All current data and examples are synthetic and are not upay BD performance evidence.
- The risk and movement values in the CLI example are illustrative inputs, not model predictions.
- Proportional taint is a bookkeeping assumption, not a fraud or ownership determination.
- Thresholds are hackathon defaults, not validated production policy or legal guidance.
- Any real hold workflow would require explicit provider, legal, regulatory, security, and operational validation.
