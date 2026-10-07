# FlowFreeze in an MFS Fraud Operations Workflow

> **Product boundary:** FlowFreeze is an intelligence and analyst decision-support layer. It is not the financial transaction engine, transaction-monitoring system, case system of record, or a wallet-control service. This repository is a synthetic demonstration; it has no production MFS connection or live action capability.

## Business value proposition

**For** MFS fraud and risk operations, **FlowFreeze** is an AI fund-flow investigation and decision-support platform **that** helps analysts detect, trace, quantify, predict, and prioritize suspicious money movement. **Unlike** simple transaction-level fraud alerts, it combines behavioral risk intelligence with multi-hop fund-flow investigation and proportionate recommendations. Any business value remains a hypothesis until validated on authorized real cases; no monetary savings or operational improvement is claimed here.

## Business actor model

| Actor | What they need from FlowFreeze | Decision rights / boundary |
|---|---|---|
| **Primary: Fraud/Risk Analyst** | A prioritized case queue, explainable signals, trace evidence, estimated exposure, likely next move, recommendation, urgency, and an auditable way to record a decision and feedback. | Reviews evidence; decides whether to monitor, investigate further, escalate, or close under MFS policy. FlowFreeze never decides or acts for them. |
| **Fraud Operations Manager** | Queue health, case volume, risk distribution, exposure indicators, investigation effort, workload, and team-level quality/harm measures. | Sets operational priorities and assigns work; interprets synthetic dashboard metrics as demonstration-only until measured. |
| **Compliance / Risk Team** | Versioned rationale, model/policy provenance, audit trail, uncertainty, access controls, limitations, and validation evidence. | Governs policy, model risk, audit, and approval gates; owns neither model output nor automated action by default. |
| **Customer Support / Dispute Team** | A path to receive appropriately authorized case context and record customer-impact, dispute, complaint, and appeal outcomes for evaluation. | Handles customer contact through existing approved processes; FlowFreeze does not contact customers. |
| **MFS Risk Platform** | In a future authorized design, a bounded, pseudonymous case/event feed and a place to return an advisory result only if governed. | Owns access, identity mapping, security, data retention, and any operational integration. This demo is not connected to it. |
| **Transaction Monitoring System** | Existing transaction-level monitoring and alert creation remain authoritative upstream. | Emits suspicious alerts through an approved interface in a future design; FlowFreeze complements rather than replaces it. |
| **Customer: MFS customer / account holder** | Fair, timely, proportionate review; protection against fraud without unnecessary restrictions; understandable recourse through existing MFS channels. | Not a user of this analyst demo. Customer impact must be measured, not inferred from generated data. |
| **Business: MFS operator** | Reduced investigation friction and better-informed, accountable decisions while protecting customers and meeting policy obligations. | Owns the business case, operating policy, customer outcomes, approvals, and go/no-go decisions. |

## Workflow placement

```text
CUSTOMER / MFS ACCOUNT ACTIVITY
                ↓
          TRANSACTION
                ↓
   TRANSACTION MONITORING SYSTEM
                ↓
       SUSPICIOUS ALERT / CASE
                ↓
     ┌──── FLOWFREEZE (ADVISORY) ────┐
     │ behavioral risk and explanation│
     │ multi-hop fund-flow tracing    │
     │ potential exposure estimate    │
     │ likely next move and urgency   │
     │ policy-aware recommendation     │
     └────────────────────────────────┘
                ↓ evidence + context
        FRAUD / RISK ANALYST
                ↓ human decision under MFS policy
   monitor | enhanced review | hold/escalate* | close
                ↓
       EXISTING MFS CASE / RISK SYSTEM
                ↓
        AUDIT + OUTCOME / FEEDBACK
                ↓
  GOVERNED MODEL / POLICY IMPROVEMENT
```

`*` Any hold/escalation is performed only through the operator's existing authorized process, after human review and policy checks. FlowFreeze itself does not execute it. In a shadow phase, its output is recorded separately and does not influence the live operational decision.

## AI output → business decision

| AI output | Business use | User | Decision supported (never automatic) |
|---|---|---|---|
| Risk score and explanation | Prioritize analyst attention and surface contributing evidence | Fraud analyst | Review now, monitor, or inspect evidence; score is not a fraud finding |
| Money-flow graph | Identify downstream exposure and investigation leads | Fraud analyst | Which wallets/transactions to inspect or refer for enhanced review |
| Tainted value | Estimate potentially exposed value with explicit attribution uncertainty | Risk manager / fraud analyst | Size and scope further investigation; not ownership, loss, or recoverable funds |
| Next move | Prioritize intervention timing and monitoring | Fraud analyst | Whether to expedite review or continue monitoring; prediction is uncertain |
| Recommendation | Support policy decision with bounded rationale and legitimate-value trade-off | Fraud analyst | Accept, reject, modify, monitor, escalate, or close under operator policy |
| Audit trail | Demonstrate who reviewed what, when, why, and with what feedback | Compliance / risk team | Audit, quality review, policy governance, and model improvement |

## Case prioritization and operational summary

The intended queue uses **CRITICAL / HIGH / MEDIUM / LOW** attention bands, ordered using a governed combination of risk, potential exposure, predicted cash-out/forwarding, and response urgency. These are attention aids, not transaction instructions. A real deployment must pre-register thresholds with the MFS operator, show missing/uncertain inputs, permit analyst override, and test queue effects. The synthetic demo does not represent validated operational thresholds.

Each case file should communicate: **what happened; why it may be risky; money potentially at risk; where the money moved; likely next move; recommended response; decision owner; deadline/urgency; and audit status.** Missing evidence is stated as unavailable, never silently treated as safe. “Investigate first when appropriate” is a valid outcome; do not freeze everything.

## Business KPIs and evidence status

| KPI | Operational definition for validation | Current status |
|---|---|---|
| Cases investigated / high-risk cases | Unique cases worked and cases in each pre-agreed attention tier per period | Synthetic case counts only |
| Potential exposure / exposure identified by tracing | Distinct case-level attributed value, direct vs multi-hop, with uncertainty and independently labeled comparison | Synthetic generated-label estimate only; not actual loss |
| Simulated prevented exposure / fraud-loss reduction | Counterfactual estimate under explicit intervention assumptions, compared with confirmed outcome in a future controlled design | Simulator only; no actual fraud loss prevented or monetary savings claimed |
| Median investigation time / response-time improvement | Measure intake-to-useful-evidence, analyst handling time, and report-to-decision from synchronized event timestamps; compare paired cases | Prototype API latency is not analyst time; synthetic timing assumptions are not observed trials |
| Analyst workload / productivity | Active caseload, handling time, cases completed, evidence reviewed, rework and escalation per analyst | Synthetic/illustrative only; real analyst trials required |
| False-positive rate | False alerts / confirmed non-fraud cases under pre-agreed independent labels | Not established on representative real MFS cases |
| Customer-harm indicators | Legitimate cases affected, unnecessary holds, legitimate value affected, proportionate interventions, complaints/appeals and time to resolution | Synthetic comparisons only; no customer outcomes observed |
| Recommendation utility | Usefulness, trace accuracy, confidence, agreement, override and missing-evidence feedback | Demo feedback is not representative trial evidence |

Do not claim actual fraud-loss reduction, response-time improvement, customer harm avoided, or monetary savings before authorized, independently measured validation. Definitions and denominators should be agreed before data review; report uncertainty and subgroup results.

## Customer protection: “Don't freeze everything.”

| Dimension | Aggressive intervention comparator | Evidence-based intervention hypothesis |
|---|---|---|
| Scope | Broad restriction based on initial alert | Investigate first; consider only evidence-supported, policy-authorized, proportionate response |
| Legitimate cases affected | Count and share of confirmed legitimate cases exposed to restriction | Measure same outcomes in paired/comparable cases; do not infer from synthetic labels |
| Unnecessary holds | Count, duration, and affected customer value | Measure actual unnecessary restrictions, reversals, disputes and resolution time |
| Legitimate value affected | Amount and duration of legitimate value restricted | Compare by case and customer segment under approved definitions |
| Proportionate interventions | Not optimized for proportionality | Share of interventions bounded to evidence and policy, with analyst rationale |

Synthetic policy comparisons can illustrate trade-offs, but cannot prove reduced harm. No automated execution; human review, existing policy, appeal/recourse, and explicit uncertainty remain essential.

## Shadow-mode architecture

1. MFS-owned monitoring/case system emits a minimized, pseudonymized, read-only case event after partner authorization.
2. A governed ingestion adapter validates schema, timestamps, event ordering, data quality, and duplicate/replay handling; identifiers are tokenized by the partner.
3. FlowFreeze computes a versioned advisory snapshot: risk/explanation, graph trace, exposure estimate, next-move prediction, and recommendation.
4. A separate evaluation store pairs FlowFreeze output with the independently recorded existing-process decision and later confirmed outcome. FlowFreeze output is hidden from operational decision-makers if required by study design.
5. Analysts/reviewers provide structured feedback only under approved trial protocols; audit records are access-controlled and retained/deleted per agreement.
6. Reporting compares paired cases for timing, tracing, utility, false positives, exposure error, workload, and customer-harm indicators, with uncertainty and subgroup review.
7. A partner-controlled kill switch stops ingestion/evaluation. Read-only credentials, network allow-lists, no payment write route, and no customer-contact route are technical requirements.

This is a proposed architecture, not an existing connection. Current repository shadow mode is a synthetic simulation only; operator decisions and outcomes remain unavailable/null.

## Real-world validation path

Follow the staged gates in [PILOT_PLAN.md](PILOT_PLAN.md): synthetic reproducibility → authorized retrospective cases → governed shadow mode → limited analyst-assisted trial → separately approved controlled evaluation. Before each phase: obtain written MFS partner authority and legal/privacy/security/compliance/operational approval; minimize and pseudonymize data; define independent labels, denominators, target thresholds, uncertainty, subgroup cuts, owners, retention, stop conditions, and customer recourse. Analysts must never be replaced as decision owners. Targets are **to be agreed with the partner**, not invented from synthetic results.

## Demo-to-business mapping

The demo should tell one end-to-end operational story: suspicious transaction arrives → FlowFreeze ranks attention → analyst sees risk and why → traces downstream money → reviews estimated exposure → sees likely next move → reviews a proportionate recommendation → records a human decision → sees only explicitly simulated business impact → verifies the audit record. Close with the evidence boundary: generated data and scenario estimates today; analyst trials and partner-authorized shadow validation required for real impact claims.
