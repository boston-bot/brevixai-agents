# Brevix AI Benchmark Report

Generated: 2026-05-17T19:33:55.815545+00:00

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
| Average Latency | 4.5 ms |

## Scenario Breakdown

| Scenario | Status | Latency (ms) | Failed Checks |
|----------|--------|--------------|---------------|
| duplicate_invoice | PASS | 7.97 | — |
| split_payments_under_threshold | PASS | 4.23 | — |
| vendor_concentration | PASS | 4.33 | — |
| round_dollar_payments | PASS | 4.6 | — |
| reconciliation_mismatch | PASS | 3.51 | — |
| ghost_vendor | PASS | 3.85 | — |
| employee_vendor_overlap | PASS | 3.86 | — |
| shared_bank_account_multiple_vendors | PASS | 3.69 | — |
| vendor_paid_before_onboarding | PASS | 3.67 | — |
| duplicate_vendor_name_variation | PASS | 3.59 | — |
| unusual_refund_activity | PASS | 4.47 | — |
| payroll_anomaly | PASS | 5.27 | — |
| weekend_after_hours_payment | PASS | 5.17 | — |
| approval_threshold_splitting | PASS | 4.89 | — |
| high_risk_vendor_concentration_over_time | PASS | 4.69 | — |

## Slowest Scenarios

| Scenario | Latency (ms) |
|----------|--------------|
| duplicate_invoice | 7.97 |
| payroll_anomaly | 5.27 |
| weekend_after_hours_payment | 5.17 |
| approval_threshold_splitting | 4.89 |
| high_risk_vendor_concentration_over_time | 4.69 |

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
