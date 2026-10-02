# Responsible AI and Model Use

FlowFreeze is an early synthetic-data hackathon prototype. Its machine-learning outputs are not evidence that a person or wallet committed fraud, and must not be used to restrict access to money or services.

## Permitted demo use

- Explore generated fund-flow scenarios and compare model output with transaction evidence.
- Show held-out synthetic evaluation with the limitations stated in the model card.
- Use analyst-approved simulated interventions to explain the review workflow.

## Prohibited interpretation

- Treat a score, graph connection, or taint estimate as proof, ownership, or legal authority to freeze funds.
- Present synthetic accuracy or value-preservation estimates as upay BD production results.
- Use real customer, phone, NID, wallet, or transaction data in this prototype.
- Let model output autonomously hold, reverse, confiscate, refund, or deny a transaction.

## Design controls

- Inference features use events visible at the recorded analysis time; generated future labels are kept out of inference.
- Model selection, decision threshold choice, and next-move calibration use validation data; reported final metrics use a held-out case split.
- Scores and estimated taint remain distinct from the policy recommendation and evidence transaction list.
- Missing score artifacts remain unavailable instead of silently defaulting to a zero-risk score.
- Analyst approve/reject/modify decisions are recorded in the local audit workflow; this does not connect to a provider ledger.

## Before any real-world research

Do not connect production data or wallet controls as a hackathon extension. A separate, formally governed project would first need authorization and legal review; representative and independently labeled data; privacy, security, retention, and access controls; out-of-time and out-of-family validation; subgroup error and calibration analysis; adversarial and operational testing; documented appeal and human-review processes; and explicit provider/regulatory approval. The current prototype does not meet those requirements.
