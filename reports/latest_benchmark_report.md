# Brevix AI Benchmark Report

Generated: 2026-05-18T01:52:35.548583+00:00

## Summary

| Metric | Value |
|--------|-------|
| Total Scenarios | 15 |
| Total Passed | 15 |
| Total Failed | 0 |
| Pass Rate | 100.0% |
| Severity Accuracy | 100.0% |
| Evidence Completeness (avg) | 100.0% |
| False Positive Clean Rate | 100.0% |
| Hallucination Failures | 0 |
| Average Latency | 8.5 ms |

## Prompt Versions

| Prompt | Version | Hash (short) |
|--------|---------|--------------|
| router | v1 | `e2c19212` |
| fraud_analyzer_summary | v1 | `77ef4951` |
| explanation | v1 | `b30b9cab` |
| action_gate | v1 | `b8e21189` |

## Scenario Breakdown

| Scenario | Status | Latency (ms) | Tags | Failed Checks |
|----------|--------|--------------|------|---------------|
| duplicate_invoice | PASS | 7.78 | vendor, duplicate, payments | — |
| split_payments_under_threshold | PASS | 4.86 | vendor, threshold, payments | — |
| vendor_concentration | PASS | 6.3 | vendor, payments | — |
| round_dollar_payments | PASS | 8.01 | vendor, payments | — |
| reconciliation_mismatch | PASS | 27.42 | reconciliation, payments | — |
| ghost_vendor | PASS | 22.68 | vendor, onboarding, entity_graph | — |
| employee_vendor_overlap | PASS | 6.76 | vendor, entity_graph | — |
| shared_bank_account_multiple_vendors | PASS | 6.01 | vendor, entity_graph, payments | — |
| vendor_paid_before_onboarding | PASS | 5.11 | vendor, onboarding | — |
| duplicate_vendor_name_variation | PASS | 4.75 | vendor, duplicate, entity_graph | — |
| unusual_refund_activity | PASS | 6.69 | vendor, payments | — |
| payroll_anomaly | PASS | 4.92 | payroll | — |
| weekend_after_hours_payment | PASS | 5.36 | after_hours, payments, vendor | — |
| approval_threshold_splitting | PASS | 5.17 | vendor, threshold, payments | — |
| high_risk_vendor_concentration_over_time | PASS | 5.44 | vendor, payments, entity_graph | — |

## Slowest Scenarios

| Scenario | Latency (ms) |
|----------|--------------|
| reconciliation_mismatch | 27.42 |
| ghost_vendor | 22.68 |
| round_dollar_payments | 8.01 |
| duplicate_invoice | 7.78 |
| employee_vendor_overlap | 6.76 |

## Failed Checks

All scenarios passed. No failures to report.

## Known Gaps

- No LLM-based evaluators — all checks are deterministic; nuanced reasoning quality is unmeasured.
- Latency benchmarks use the deterministic model provider; real LLM latency will differ significantly.
- Dataset covers 16 scenarios; edge cases like multi-fraud overlaps are not yet represented.
- No cross-scenario confusion testing (a scenario triggering a different scenario's pattern).
- Evidence ID validation relies on tool fixture; does not test evidence retrieval accuracy end-to-end.

## Next Recommended Improvements

- Add LLM-as-judge evaluation for response reasoning quality and explanation clarity.
- Expand dataset to cover compound fraud patterns (e.g., duplicate + split threshold).
- Add latency benchmarks against the real model provider to establish production SLOs.
- Introduce mutation testing: perturb fixtures to verify evaluators catch regressions.
- Add a trend report comparing multiple eval runs over time to surface score drift.
