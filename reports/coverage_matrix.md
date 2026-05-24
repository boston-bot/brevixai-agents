# Brevix AI Benchmark Coverage Matrix

Generated: 2026-05-19T00:42:56.696794+00:00

## Summary

| Metric | Count |
|--------|-------|
| Total scenarios | 21 |
| Categories | 4 |
| Risk types | 14 |
| Severity levels | 3 |
| Unique tags | 12 |

## Category Coverage

| Category | Scenarios |
|----------|-----------|
| accounts_payable | 9 |
| vendor_management | 9 |
| accounting | 2 |
| payroll | 1 |

## Risk Type Coverage

| Risk Type | Scenarios |
|-----------|-----------|
| multi_domain_synthesis | 5 |
| threshold_evasion | 2 |
| unusual_payment_pattern | 2 |
| vendor_concentration | 2 |
| conflict_of_interest | 1 |
| control_bypass | 1 |
| duplicate_invoice | 1 |
| duplicate_vendor | 1 |
| false_correlation_suppression | 1 |
| ghost_vendor | 1 |
| payroll_fraud | 1 |
| reconciliation_error | 1 |
| refund_fraud | 1 |
| shell_entity | 1 |

## Severity Coverage

| Severity | Scenarios |
|----------|-----------|
| high | 14 |
| critical | 4 |
| medium | 3 |

## Tag Coverage

| Tag | Scenarios |
|-----|-----------|
| vendor | 18 |
| payments | 14 |
| entity_graph | 8 |
| multi_domain | 6 |
| synthesis | 6 |
| duplicate | 3 |
| onboarding | 3 |
| reconciliation | 3 |
| threshold | 3 |
| after_hours | 1 |
| false_positive_guardrail | 1 |
| payroll | 1 |

## Data Quality Checks

| Check | Status | Detail |
|-------|--------|--------|
| Duplicate scenario IDs | PASS | None found |
| Missing evidence patterns | PASS | None found |
| Missing false-positive guardrails | PASS | None found |
| Missing recommended tags | PASS | All recommended tags covered |

## Recommended Gaps to Fill Next

- Severity `low` has no coverage — consider adding a scenario at this severity level.
- Category `payroll` has only 1 scenario — thin coverage increases regression risk.
