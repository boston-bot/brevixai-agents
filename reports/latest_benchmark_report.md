# Brevix AI Benchmark Report

Generated: 2026-05-17T19:44:21.409386+00:00

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
| Average Latency | 3.3 ms |

## Scenario Breakdown

| Scenario | Status | Latency (ms) | Failed Checks |
|----------|--------|--------------|---------------|
| duplicate_invoice | PASS | 6.41 | — |
| split_payments_under_threshold | PASS | 3.29 | — |
| vendor_concentration | PASS | 3.23 | — |
| round_dollar_payments | PASS | 3.83 | — |
| reconciliation_mismatch | PASS | 3.24 | — |
| ghost_vendor | PASS | 3.0 | — |
| employee_vendor_overlap | PASS | 2.9 | — |
| shared_bank_account_multiple_vendors | PASS | 2.85 | — |
| vendor_paid_before_onboarding | PASS | 2.98 | — |
| duplicate_vendor_name_variation | PASS | 2.9 | — |
| unusual_refund_activity | PASS | 3.34 | — |
| payroll_anomaly | PASS | 3.09 | — |
| weekend_after_hours_payment | PASS | 2.95 | — |
| approval_threshold_splitting | PASS | 2.94 | — |
| high_risk_vendor_concentration_over_time | PASS | 2.96 | — |

## Slowest Scenarios

| Scenario | Latency (ms) |
|----------|--------------|
| duplicate_invoice | 6.41 |
| round_dollar_payments | 3.83 |
| unusual_refund_activity | 3.34 |
| split_payments_under_threshold | 3.29 |
| reconciliation_mismatch | 3.24 |

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
