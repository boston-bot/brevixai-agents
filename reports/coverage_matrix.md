# Brevix AI Benchmark Coverage Matrix

Generated: 2026-05-17T21:15:09.180850+00:00

## Summary

| Metric | Count |
|--------|-------|
| Total scenarios | 15 |
| Categories | 4 |
| Risk types | 12 |
| Severity levels | 3 |
| Unique tags | 9 |

## Category Coverage

| Category | Scenarios |
|----------|-----------|
| accounts_payable | 8 |
| vendor_management | 5 |
| accounting | 1 |
| payroll | 1 |

## Risk Type Coverage

| Risk Type | Scenarios |
|-----------|-----------|
| threshold_evasion | 2 |
| unusual_payment_pattern | 2 |
| vendor_concentration | 2 |
| conflict_of_interest | 1 |
| control_bypass | 1 |
| duplicate_invoice | 1 |
| duplicate_vendor | 1 |
| ghost_vendor | 1 |
| payroll_fraud | 1 |
| reconciliation_error | 1 |
| refund_fraud | 1 |
| shell_entity | 1 |

## Severity Coverage

| Severity | Scenarios |
|----------|-----------|
| high | 10 |
| critical | 3 |
| medium | 2 |

## Tag Coverage

| Tag | Scenarios |
|-----|-----------|
| vendor | 13 |
| payments | 10 |
| entity_graph | 5 |
| duplicate | 2 |
| onboarding | 2 |
| threshold | 2 |
| after_hours | 1 |
| payroll | 1 |
| reconciliation | 1 |

## Data Quality Checks

| Check | Status | Detail |
|-------|--------|--------|
| Duplicate scenario IDs | PASS | None found |
| Missing evidence patterns | PASS | None found |
| Missing false-positive guardrails | PASS | None found |
| Missing recommended tags | FAIL | `false_positive_guardrail` |

## Recommended Gaps to Fill Next

- Tag `false_positive_guardrail` has 0 scenarios — add at least one scenario that exercises this pattern.
- Severity `low` has no coverage — consider adding a scenario at this severity level.
- Category `accounting` has only 1 scenario — thin coverage increases regression risk.
- Category `payroll` has only 1 scenario — thin coverage increases regression risk.
