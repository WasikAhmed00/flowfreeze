# FlowFreeze Analyst Trial Guide

> **Purpose:** Evaluate whether FlowFreeze supports MFS fraud investigation work. This is a research instrument for a future authorized analyst trial, not evidence of existing benefits. Do not enter real customer identifiers into the current synthetic demo.

## Trial setup

- **Participants:** MFS-authorized fraud analysts, an operations manager, evaluation lead, and customer-harm/compliance reviewers.
- **Cases:** Partner-selected, minimized and pseudonymized cases with an independently agreed label/outcome protocol. Use a suitable baseline/current-process comparison; avoid exposing FlowFreeze output when the study design requires independent decisions.
- **Protocol:** Pre-register tasks, sampling, denominators, metrics, uncertainty reporting, subgroup analysis, and target thresholds before evaluating results. Thresholds are **to be agreed with the MFS partner**; do not derive success claims from synthetic demo metrics.
- **Timing:** Record start/end timestamps for intake, first useful signal, downstream trace, exposure estimate, decision, and total handling time. Separate API processing time from analyst time.
- **Safety:** No real account action through FlowFreeze. Any operational hold/escalation remains under existing MFS policy and human authority. Use approved privacy/security controls, retention, access logging, stop criteria, and customer recourse.

## Case review questionnaire

For each case, capture response, confidence (low / medium / high), short rationale, and optional missing evidence.

1. Did FlowFreeze identify useful evidence faster than your usual workflow? What evidence and how much time did it save or add?
2. Did the graph reveal downstream wallets or movement you would otherwise miss? Which paths were accurate or misleading?
3. Was the estimated exposure useful for investigation? How did it compare with the independently reviewed case outcome or reference estimate?
4. Was the next-move prediction useful for prioritizing attention? Did it help, arrive too late, or distract?
5. Was the recommendation appropriate, proportionate, and consistent with policy? What would you accept, reject, or modify?
6. Did FlowFreeze reduce investigation effort? Record measured handling time and work performed; do not infer from model/API latency.
7. Did it create unnecessary alerts, investigations, or escalation? Record the case and operational consequence.
8. Would you trust FlowFreeze as analyst decision support? What evidence, uncertainty, or governance would change your answer?
9. What evidence was missing, incorrect, stale, or difficult to interpret?
10. What would make this usable in your workflow (integration, controls, latency, case context, training, audit, or other)?

## Per-case record

| Field | Entry |
|---|---|
| Pseudonymous case key / study arm | |
| Analyst role / experience band (no direct identifier) | |
| Case label and adjudication status | |
| FlowFreeze model, policy, and configuration version | |
| Time to first useful signal / trace / exposure / decision | |
| Total analyst handling time and evidence reviewed | |
| Trace accuracy / downstream evidence findings | |
| Exposure estimate and reference; absolute/relative error | |
| Next-move utility and confidence | |
| Recommendation usefulness / agreement / override | |
| False alert or missed-case finding | |
| Legitimate case affected / unnecessary hold / legitimate value affected | |
| Proportionate intervention and customer-harm outcome | |
| Missing evidence, rationale, and free-text feedback | |

Use only approved, minimized data. Capture customer harm and appeal/dispute outcomes where authorized; null means unavailable, never zero harm.

## Trial KPIs and analysis

Report paired-case distributions and uncertainty intervals for median investigation time, first useful signal, trace accuracy, additional downstream evidence, exposure-estimate error, analyst workload, recommendation usefulness/agreement/override, false-positive and false-negative rates, legitimate cases affected, unnecessary holds, legitimate value affected, and proportionate interventions. Predefine case inclusion, label adjudication, handling of missing data, subgroup cuts, and stopping rules. Do not present correlations or synthetic counterfactuals as causal impact.

## Decision and stop criteria

At trial close, document results including negative and inconclusive findings. Compare them with partner-approved targets and customer-harm boundaries. Pause immediately for privacy/security incidents, unreliable data, unsafe recommendations, unexplained subgroup disparities, material customer harm, audit gaps, or partner request. Progression requires a written partner go/no-go; this guide grants no data access or deployment authorization.
