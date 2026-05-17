# Brevix AI Benchmark Report

Generated: 2026-05-17T19:47:32.973581+00:00

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
| Average Latency | 4.6 ms |

## Scenario Breakdown

| Scenario | Status | Latency (ms) | Failed Checks |
|----------|--------|--------------|---------------|
| duplicate_invoice | PASS | 5.68 | — |
| split_payments_under_threshold | PASS | 4.8 | — |
| vendor_concentration | PASS | 4.08 | — |
| round_dollar_payments | PASS | 4.78 | — |
| reconciliation_mismatch | PASS | 4.07 | — |
| ghost_vendor | PASS | 3.94 | — |
| employee_vendor_overlap | PASS | 3.77 | — |
| shared_bank_account_multiple_vendors | PASS | 3.82 | — |
| vendor_paid_before_onboarding | PASS | 4.18 | — |
| duplicate_vendor_name_variation | PASS | 4.76 | — |
| unusual_refund_activity | PASS | 4.15 | — |
| payroll_anomaly | PASS | 5.12 | — |
| weekend_after_hours_payment | PASS | 5.25 | — |
| approval_threshold_splitting | PASS | 5.79 | — |
| high_risk_vendor_concentration_over_time | PASS | 4.98 | — |

## Slowest Scenarios

| Scenario | Latency (ms) |
|----------|--------------|
| approval_threshold_splitting | 5.79 |
| duplicate_invoice | 5.68 |
| weekend_after_hours_payment | 5.25 |
| payroll_anomaly | 5.12 |
| high_risk_vendor_concentration_over_time | 4.98 |

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
