# Brevix AI Benchmark Report

Generated: 2026-05-23T20:44:38.136167+00:00

## Summary

| Metric | Value |
|--------|-------|
| Total Scenarios | 21 |
| Total Passed | 21 |
| Total Failed | 0 |
| Pass Rate | 100.0% |
| Severity Accuracy | 100.0% |
| Evidence Completeness (avg) | 100.0% |
| False Positive Clean Rate | 100.0% |
| Hallucination Failures | 0 |
| Average Latency | 4.2 ms |

## Prompt Versions

| Prompt | Version | Hash (short) |
|--------|---------|--------------|
| router | v1 | `846a128c` |
| fraud_analyzer_summary | v1 | `77ef4951` |
| investigation_synthesis | v1 | `8fd0ee65` |
| explanation | v2 | `937f7ca8` |
| action_gate | v2 | `0fd74891` |

## Scenario Breakdown

| Scenario | Status | Latency (ms) | Tags | Failed Checks |
|----------|--------|--------------|------|---------------|
| duplicate_invoice | PASS | 7.46 | vendor, duplicate, payments | — |
| split_payments_under_threshold | PASS | 4.29 | vendor, threshold, payments | — |
| vendor_concentration | PASS | 4.1 | vendor, payments | — |
| round_dollar_payments | PASS | 4.91 | vendor, payments | — |
| reconciliation_mismatch | PASS | 3.95 | reconciliation, payments | — |
| ghost_vendor | PASS | 3.61 | vendor, onboarding, entity_graph | — |
| employee_vendor_overlap | PASS | 3.91 | vendor, entity_graph | — |
| shared_bank_account_multiple_vendors | PASS | 3.71 | vendor, entity_graph, payments | — |
| vendor_paid_before_onboarding | PASS | 3.95 | vendor, onboarding | — |
| duplicate_vendor_name_variation | PASS | 3.72 | vendor, duplicate, entity_graph | — |
| unusual_refund_activity | PASS | 3.9 | vendor, payments | — |
| payroll_anomaly | PASS | 3.69 | payroll | — |
| weekend_after_hours_payment | PASS | 3.98 | after_hours, payments, vendor | — |
| approval_threshold_splitting | PASS | 3.82 | vendor, threshold, payments | — |
| high_risk_vendor_concentration_over_time | PASS | 4.01 | vendor, payments, entity_graph | — |
| phase4_vendor_entity_overlap_synthesis | PASS | 4.22 | vendor, entity_graph, multi_domain, synthesis | — |
| phase4_reconciliation_threshold_synthesis | PASS | 4.05 | reconciliation, threshold, payments, multi_domain, synthesis | — |
| phase4_rapid_onboarding_round_dollar_synthesis | PASS | 3.93 | vendor, onboarding, payments, multi_domain, synthesis | — |
| phase4_duplicate_vendor_shared_account_synthesis | PASS | 4.18 | vendor, duplicate, entity_graph, payments, multi_domain, synthesis | — |
| phase4_unsupported_correlation_suppression | PASS | 4.39 | vendor, entity_graph, false_positive_guardrail, multi_domain, synthesis | — |
| phase4_multiple_medium_risk_elevation | PASS | 4.27 | vendor, reconciliation, payments, multi_domain, synthesis | — |

## Slowest Scenarios

| Scenario | Latency (ms) |
|----------|--------------|
| duplicate_invoice | 7.46 |
| round_dollar_payments | 4.91 |
| phase4_unsupported_correlation_suppression | 4.39 |
| split_payments_under_threshold | 4.29 |
| phase4_multiple_medium_risk_elevation | 4.27 |

## Failed Checks

All scenarios passed. No failures to report.

## Known Gaps

- No LLM-based evaluators — all checks are deterministic; nuanced reasoning quality is unmeasured.
- Latency benchmarks use the deterministic model provider; real LLM latency will differ significantly.
- Synthesis benchmarks use synthetic deterministic fixtures rather than live Laravel evidence retrieval.
- Cross-scenario confusion testing is limited to guardrail terms and unsupported-correlation fixtures.
- Evidence ID validation relies on tool fixtures and does not verify source-system persistence.

## Next Recommended Improvements

- Add LLM-as-judge evaluation for response reasoning quality and explanation clarity.
- Expand synthesis fixtures with more conflicting-domain and partial-evidence cases.
- Add latency benchmarks against the real model provider to establish production SLOs.
- Introduce mutation testing: perturb fixtures to verify evaluators catch regressions.
- Add a trend report comparing multiple eval runs over time to surface score drift.
