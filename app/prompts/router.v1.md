---
name: router
version: v1
---

Classify the following user message into one intent category.

Available intents:
- fraud_pattern_search: message concerns fraud, suspicious activity, vendor risk, payment anomalies, invoice irregularities, duplicate payments, threshold breaches, transaction splits, or vendor concentration.
- reconciliation_review: message concerns reconciliation, unmatched transactions, or accounting mismatches.
- unknown_or_unsupported: message does not match a supported intent.

Signals for fraud_pattern_search: fraud, suspicious, vendor, risk, alert, anomaly, payment, invoice, duplicate, threshold, split, concentration.
Signals for reconciliation_review: reconciliation, unmatched, mismatch.

Message: {{message}}

Respond with exactly one intent label.
