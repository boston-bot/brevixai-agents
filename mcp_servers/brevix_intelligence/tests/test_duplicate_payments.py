"""Tests for duplicate payment detection — pure analysis logic, no HTTP calls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_servers.brevix_intelligence.tools.duplicate_payments import _analyze_duplicates

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture_transactions() -> list[dict]:
    data = json.loads((FIXTURES_DIR / "transactions.json").read_text())
    return data["transactions"]


class TestAnalyzeDuplicates:
    def test_detects_exact_amount_and_same_invoice(self):
        transactions = [
            {"id": "t1", "vendor": "ABC Supply", "amount": 1840.22, "date": "2026-04-01", "invoice_number": "INV-001"},
            {"id": "t2", "vendor": "ABC Supply", "amount": 1840.22, "date": "2026-04-05", "invoice_number": "INV-001"},
        ]
        findings = _analyze_duplicates(transactions, amount_tolerance=0.01, date_window_days=30)
        assert len(findings) == 1
        assert findings[0].risk_type == "duplicate_payment"
        assert findings[0].confidence >= 0.70
        assert len(findings[0].evidence) == 2

    def test_detects_exact_amount_without_invoice(self):
        transactions = [
            {"id": "t1", "vendor": "ABC Supply", "amount": 500.00, "date": "2026-04-01"},
            {"id": "t2", "vendor": "ABC Supply", "amount": 500.00, "date": "2026-04-03"},
        ]
        findings = _analyze_duplicates(transactions, amount_tolerance=0.01, date_window_days=30)
        assert len(findings) == 1
        assert findings[0].confidence >= 0.50

    def test_no_duplicate_different_vendors(self):
        transactions = [
            {"id": "t1", "vendor": "ABC Supply", "amount": 1840.22, "date": "2026-04-01"},
            {"id": "t2", "vendor": "XYZ Corp", "amount": 1840.22, "date": "2026-04-01"},
        ]
        findings = _analyze_duplicates(transactions, amount_tolerance=0.01, date_window_days=30)
        assert len(findings) == 0

    def test_no_duplicate_date_outside_window(self):
        transactions = [
            {"id": "t1", "vendor": "ABC Supply", "amount": 1840.22, "date": "2026-01-01"},
            {"id": "t2", "vendor": "ABC Supply", "amount": 1840.22, "date": "2026-04-01"},
        ]
        # 90 days apart, window is 30 days
        findings = _analyze_duplicates(transactions, amount_tolerance=0.01, date_window_days=30)
        assert len(findings) == 0

    def test_no_duplicate_amount_too_different(self):
        transactions = [
            {"id": "t1", "vendor": "ABC Supply", "amount": 1000.00, "date": "2026-04-01"},
            {"id": "t2", "vendor": "ABC Supply", "amount": 1500.00, "date": "2026-04-02"},
        ]
        findings = _analyze_duplicates(transactions, amount_tolerance=0.01, date_window_days=30)
        assert len(findings) == 0

    def test_no_duplicate_negative_or_zero_amounts(self):
        transactions = [
            {"id": "t1", "vendor": "ABC Supply", "amount": 0, "date": "2026-04-01"},
            {"id": "t2", "vendor": "ABC Supply", "amount": -100, "date": "2026-04-02"},
        ]
        findings = _analyze_duplicates(transactions, amount_tolerance=0.01, date_window_days=30)
        assert len(findings) == 0

    def test_pairs_not_double_counted(self):
        transactions = [
            {"id": "t1", "vendor": "ABC Supply", "amount": 500.00, "date": "2026-04-01"},
            {"id": "t2", "vendor": "ABC Supply", "amount": 500.00, "date": "2026-04-02"},
        ]
        findings = _analyze_duplicates(transactions, amount_tolerance=0.01, date_window_days=30)
        assert len(findings) == 1  # not 2

    def test_confidence_higher_with_matching_invoice_and_memo(self):
        transactions_with_match = [
            {"id": "t1", "vendor": "V", "amount": 100.00, "date": "2026-04-01", "invoice_number": "INV-X", "memo": "Same memo"},
            {"id": "t2", "vendor": "V", "amount": 100.00, "date": "2026-04-02", "invoice_number": "INV-X", "memo": "Same memo"},
        ]
        transactions_no_match = [
            {"id": "t3", "vendor": "V", "amount": 100.00, "date": "2026-04-01"},
            {"id": "t4", "vendor": "V", "amount": 100.00, "date": "2026-04-02"},
        ]
        findings_with = _analyze_duplicates(transactions_with_match, 0.01, 30)
        findings_without = _analyze_duplicates(transactions_no_match, 0.01, 30)
        assert findings_with[0].confidence > findings_without[0].confidence

    def test_fixture_detects_both_duplicate_pairs(self):
        transactions = [
            t for t in load_fixture_transactions()
            if t["vendor"] in ("ABC Supply Co", "Northstar Consulting")
        ]
        findings = _analyze_duplicates(transactions, amount_tolerance=0.01, date_window_days=30)
        assert len(findings) >= 2

    def test_evidence_contains_both_transaction_ids(self):
        transactions = [
            {"id": "t1", "vendor": "Vendor A", "amount": 200.00, "date": "2026-04-01"},
            {"id": "t2", "vendor": "Vendor A", "amount": 200.00, "date": "2026-04-03"},
        ]
        findings = _analyze_duplicates(transactions, 0.01, 30)
        assert len(findings) == 1
        evidence_ids = {e.transaction_id for e in findings[0].evidence}
        assert "t1" in evidence_ids
        assert "t2" in evidence_ids

    def test_recommended_next_steps_present(self):
        transactions = [
            {"id": "t1", "vendor": "V", "amount": 100.00, "date": "2026-04-01"},
            {"id": "t2", "vendor": "V", "amount": 100.00, "date": "2026-04-02"},
        ]
        findings = _analyze_duplicates(transactions, 0.01, 30)
        assert len(findings[0].recommended_next_steps) > 0

    def test_vendor_name_normalization(self):
        """Vendor names differing only by case and whitespace should be grouped."""
        transactions = [
            {"id": "t1", "vendor": "  ABC SUPPLY  ", "amount": 100.00, "date": "2026-04-01"},
            {"id": "t2", "vendor": "abc supply", "amount": 100.00, "date": "2026-04-02"},
        ]
        findings = _analyze_duplicates(transactions, 0.01, 30)
        assert len(findings) == 1

    def test_empty_transactions(self):
        findings = _analyze_duplicates([], 0.01, 30)
        assert findings == []

    def test_single_transaction(self):
        transactions = [{"id": "t1", "vendor": "V", "amount": 100.00, "date": "2026-04-01"}]
        findings = _analyze_duplicates(transactions, 0.01, 30)
        assert findings == []
