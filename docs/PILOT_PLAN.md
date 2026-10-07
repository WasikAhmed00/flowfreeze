# FlowFreeze Pilot Plan

> **No phase implies approval to use real MFS data or operate on customer accounts.** Each real-data phase requires MFS partner authorization plus legal, privacy, security, compliance and operational review. Success thresholds remain configurable and must be agreed with the partner; this plan intentionally invents no target percentages.

## Target-setting principle

Every numeric success threshold is **TARGET TO BE AGREED DURING PILOT**. Before each phase, the partner and evaluation owner should specify baseline, denominator, measurement window, confidence/uncertainty reporting, subgroup cuts, owner, and decision rule for:

- median investigation-time reduction;
- downstream exposure identified versus the current process;
- unnecessary-hold / false-positive reduction (only when actual intervention outcomes are authorized and observable);
- analyst acceptance/agreement and override rate;
- cash-out detection recall and false-positive rate;
- recommendation usefulness, trace accuracy, analyst confidence;
- reliability, data quality, privacy/security incidents, and customer-harm indicators.

Targets must be signed off before outcome review, not retrofitted to the results. The configurable `core/pilot_targets.json` starts with null values that represent unagreed targets, not zero-goal success. Update them only after partner approval and document the metric definition/version.

## Phase 0 — Synthetic validation

- **Data:** Repository-generated transactions, incidents, wallet records and generator labels only.
- **Duration:** Until reproducibility, test coverage, and agreed synthetic scenarios are complete; schedule set by the project team.
- **Participants:** FlowFreeze engineering, fraud-operations design reviewer, privacy/security reviewer; no customer records.
- **Success metrics:** Deterministic replay; documented synthetic precision/recall/PR-AUC; graph and exposure calculations; no-actuation tests; feedback audit tests; documented known limitations. No production-performance target.
- **Safety controls:** Offline/synthetic inputs; no payment integration; no customer contact; no real identifiers; no action-capable credentials.
- **Stop criteria:** Any unexplained synthetic leakage, double-counting, incorrect auditability, code path capable of external financial/customer action, or failed safety test blocks progression.

## Phase 1 — Retrospective real-case validation

- **Data:** Partner-selected historical, minimized, pseudonymized and independently labeled cases, with required outcome, intervention, transaction/cash-out and timestamp fields where available.
- **Duration:** Partner-selected sampling window sized to support pre-registered metrics and relevant segments; determine before analysis.
- **Participants:** Partner fraud operations, independent label adjudicators, data owner, privacy/legal, security, model-risk/evaluation owner.
- **Success metrics:** Pre-registered precision, recall, PR-AUC, calibration, subgroup error analysis, trace accuracy, exposure-estimate agreement, time-replay feasibility and comparison with current decisions. All numerical acceptance criteria are **TARGET TO BE AGREED DURING PILOT**.
- **Safety controls:** Approved secure environment, access and retention restrictions, audit log, pseudonymization, least privilege, no operational feedback to customer/accounts, independent label protocol.
- **Stop criteria:** Authorization lapse; re-identification risk; material label disagreement; data quality insufficient for planned denominator; leakage; security incident; or any request to take live action.

## Phase 2 — Shadow deployment

- **Data:** Authorized live or near-live, minimized pseudonymous case/event feed, paired with the existing operational case and decision records. Read-only data access only.
- **Duration:** Partner-agreed observation window spanning the required volume, operational cycles, and case segments; no fixed duration is assumed here.
- **Participants:** Partner operations owner and analysts, data/platform owners, security/privacy/compliance, FlowFreeze evaluation lead, named incident/stop authority.
- **Success metrics:** Paired case coverage; feed completeness/latency; precision/recall/PR-AUC against independently confirmed outcomes; median time-to-signal/trace; exposure estimate difference; analyst agreement/override/usefulness/confidence where collected; false-positive/customer-harm indicators. Pre-agreed thresholds remain **TARGET TO BE AGREED DURING PILOT**.
- **Safety controls:** No write credentials or payment-system action route; recommendations hidden or clearly marked advisory per design; model/config versioning; data minimization and retention; case-level audit; independent current-process decisions; immediate ingestion kill switch.
- **Stop criteria:** Any attempted external action; feed/data integrity issue; privacy/security event; out-of-scope identifiers; threshold/drift breach as pre-agreed; unreviewed recommendation entering operational queues; or partner stop request.

## Phase 3 — Analyst-assisted pilot

- **Data:** Approved pseudonymous cases and FlowFreeze advisory output paired with analyst review and feedback. Existing operations continue independently; any operational intervention remains under the partner's normal authorization and control.
- **Duration:** Partner-agreed limited cohort and review window, selected to avoid unsupported extrapolation.
- **Participants:** Trained, consenting/authorized analyst cohort; supervisor; partner fraud owner; independent evaluation and customer-harm reviewer; privacy/security/compliance.
- **Success metrics:** Analyst review time, usefulness, trace accuracy, confidence, recommendation acceptance/override, downstream exposure visibility, recall/false positives, and legitimate-value/hold outcome measures where available. Targets and segment-specific stop bounds are **TARGET TO BE AGREED DURING PILOT**.
- **Safety controls:** Training and uncertainty display; human decision remains authoritative; rationale and feedback audit; bounded cohort; escalation and appeal path; no automatic action; daily monitoring and rollback.
- **Stop criteria:** Pre-agreed customer-harm or false-positive boundary crossed; material analyst over-reliance or workflow confusion; data drift or missingness; unsafe recommendation; audit failure; incident or partner request.

## Phase 4 — Controlled production evaluation

- **Data:** Only data and outcomes explicitly authorized for a controlled evaluation; compare to a suitable concurrent or otherwise defensible control design approved by partner governance.
- **Duration:** Determined by pre-analysis power/precision planning, operational seasonality and partner approval; not set by this prototype.
- **Participants:** Partner accountable executive and operations owner, analytics/statistics lead, independent risk/customer-harm reviewers, legal/privacy/security/compliance, approved analysts.
- **Success metrics:** Pre-registered business and human KPIs, causal/controlled comparison, uncertainty intervals, subgroup and calibration monitoring, operational reliability, customer impact and complaint/appeal outcomes. All material thresholds are **TARGET TO BE AGREED DURING PILOT**.
- **Safety controls:** Separate production authorization and risk assessment; strict human-in-the-loop decision rights; no autonomy unless separately authorized through governance; access control, audit, monitoring, incident handling, appeals and rollback plan.
- **Stop criteria:** Any harm boundary breach, unexplained disparity, performance below partner-agreed criteria, control contamination, model/data drift, privacy/security issue, or inability to audit/rollback.

## Decision gates and ownership

Each phase ends with a written go/no-go decision. The MFS partner owns data authority, operational policy, target approval and stop authority. FlowFreeze owns implementation transparency, versioning, reproducible evaluation, safety boundaries and timely reporting of adverse/negative findings. No phase progression is automatic; passing synthetic tests does not establish readiness for a real deployment.
