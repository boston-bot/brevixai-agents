# Brevix AI Benchmark Report

Generated: 2026-05-17T19:59:43.653131+00:00

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
| Average Latency | 4.7 ms |

## Scenario Breakdown

| Scenario | Status | Latency (ms) | Failed Checks |
|----------|--------|--------------|---------------|
| duplicate_invoice | PASS | 9.85 | — |
| split_payments_under_threshold | PASS | 4.76 | — |
| vendor_concentration | PASS | 3.8 | — |
| round_dollar_payments | PASS | 4.87 | — |
| reconciliation_mismatch | PASS | 4.09 | — |
| ghost_vendor | PASS | 4.45 | — |
| employee_vendor_overlap | PASS | 3.79 | — |
| shared_bank_account_multiple_vendors | PASS | 3.72 | — |
| vendor_paid_before_onboarding | PASS | 3.76 | — |
| duplicate_vendor_name_variation | PASS | 5.17 | — |
| unusual_refund_activity | PASS | 4.92 | — |
| payroll_anomaly | PASS | 4.22 | — |
| weekend_after_hours_payment | PASS | 4.01 | — |
| approval_threshold_splitting | PASS | 4.68 | — |
| high_risk_vendor_concentration_over_time | PASS | 4.48 | — |

## Slowest Scenarios

| Scenario | Latency (ms) |
|----------|--------------|
| duplicate_invoice | 9.85 |
| duplicate_vendor_name_variation | 5.17 |
| unusual_refund_activity | 4.92 |
| round_dollar_payments | 4.87 |
| split_payments_under_threshold | 4.76 |

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
