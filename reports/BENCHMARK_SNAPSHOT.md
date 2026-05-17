# Brevix AI Benchmark Snapshot

**Service Version:** 0.1.0
**Generated:** 2026-05-17T19:59:43.653131+00:00
**Scenarios run:** 15

---

## Release Readiness

**Status: READY** — All quality gate thresholds passed.

---

## Quality Metrics

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Pass Rate | 100.0% | ≥ 95% | PASS |
| Severity Accuracy | 100.0% | ≥ 95% | PASS |
| Evidence Completeness (avg) | 100.0% | ≥ 90% | PASS |
| False Positive Clean Rate | 100.0% | ≥ 95% | PASS |
| Hallucination Failures | 0 | ≤ 0 | PASS |
| Average Latency | 4.7 ms | ≤ 500.0 ms | PASS |

---

## Dataset Coverage

**Total scenarios run:** 15

**Categories covered:**

| Category | Scenarios |
|----------|-----------|
| accounting | 1 |
| accounts_payable | 8 |
| payroll | 1 |
| vendor_management | 5 |

---

## Slowest Scenarios

| Scenario | Latency (ms) |
|----------|--------------| 
| duplicate_invoice | 9.85 |
| duplicate_vendor_name_variation | 5.17 |
| unusual_refund_activity | 4.92 |
| round_dollar_payments | 4.87 |
| split_payments_under_threshold | 4.76 |

---

## Known Gaps

- No LLM-based evaluators — all checks are deterministic; nuanced reasoning quality is unmeasured.
- Latency benchmarks use the deterministic model provider; real LLM latency will differ significantly.
- Dataset covers 16 scenarios; edge cases like multi-fraud overlaps are not yet represented.
- No cross-scenario confusion testing (a scenario triggering a different scenario's pattern).
- Evidence ID validation relies on tool fixture; does not test evidence retrieval accuracy end-to-end.
