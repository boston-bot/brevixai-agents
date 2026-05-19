# Brevix AI Benchmark Snapshot

**Service Version:** 0.1.0
**Generated:** 2026-05-19T00:43:50.275087+00:00
**Scenarios run:** 21

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
| Average Latency | 5.1 ms | ≤ 500.0 ms | PASS |

---

## Dataset Coverage

**Total scenarios run:** 21

**Categories covered:**

| Category | Scenarios |
|----------|-----------|
| accounting | 2 |
| accounts_payable | 9 |
| payroll | 1 |
| vendor_management | 9 |

---

## Slowest Scenarios

| Scenario | Latency (ms) |
|----------|--------------| 
| duplicate_invoice | 7.38 |
| phase4_multiple_medium_risk_elevation | 5.68 |
| phase4_rapid_onboarding_round_dollar_synthesis | 5.34 |
| vendor_paid_before_onboarding | 5.24 |
| phase4_vendor_entity_overlap_synthesis | 5.21 |

---

## Prompt Versions

| Prompt | Version | Hash (short) |
|--------|---------|--------------|
| router | v1 | `846a128c` |
| fraud_analyzer_summary | v1 | `77ef4951` |
| investigation_synthesis | v1 | `8fd0ee65` |
| explanation | v1 | `b30b9cab` |
| action_gate | v1 | `b8e21189` |

---

## Known Gaps

- No LLM-based evaluators — all checks are deterministic; nuanced reasoning quality is unmeasured.
- Latency benchmarks use the deterministic model provider; real LLM latency will differ significantly.
- Synthesis benchmarks use synthetic deterministic fixtures rather than live Laravel evidence retrieval.
- Cross-scenario confusion testing is limited to guardrail terms and unsupported-correlation fixtures.
- Evidence ID validation relies on tool fixtures and does not verify source-system persistence.
