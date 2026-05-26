"""Tests for vendor concentration analysis — pure analysis logic, no HTTP calls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_servers.brevix_intelligence.tools.vendor_concentration import _analyze_concentration

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture_transactions() -> list[dict]:
    data = json.loads((FIXTURES_DIR / "transactions.json").read_text())
    return data["transactions"]


class TestAnalyzeConcentration:
    def test_detects_dominant_vendor(self):
        transactions = [
            {"id": "t1", "vendor": "MegaVendor", "amount": 7000, "date": "2026-04-01"},
            {"id": "t2", "vendor": "MegaVendor", "amount": 8000, "date": "2026-04-10"},
            {"id": "t3", "vendor": "Small Vendor A", "amount": 1000, "date": "2026-04-15"},
            {"id": "t4", "vendor": "Small Vendor B", "amount": 4000, "date": "2026-04-20"},
        ]
        # MegaVendor = 15000/20000 = 75%
        findings = _analyze_concentration(transactions, threshold=0.30)
        assert len(findings) == 1
        assert findings[0].risk_type == "vendor_concentration"
        assert findings[0].metadata["vendor"] == "MegaVendor"
        assert findings[0].metadata["concentration_pct"] == pytest.approx(0.75, abs=0.01)

    def test_no_finding_below_threshold(self):
        transactions = [
            {"id": f"t{i}", "vendor": f"Vendor {i}", "amount": 1000, "date": "2026-04-01"}
            for i in range(5)
        ]
        # Each vendor = 20% of spend, below 30% threshold
        findings = _analyze_concentration(transactions, threshold=0.30)
        assert len(findings) == 0

    def test_multiple_vendors_above_threshold(self):
        transactions = [
            {"id": "t1", "vendor": "Vendor A", "amount": 4000, "date": "2026-04-01"},
            {"id": "t2", "vendor": "Vendor A", "amount": 4000, "date": "2026-04-05"},
            {"id": "t3", "vendor": "Vendor B", "amount": 3000, "date": "2026-04-10"},
            {"id": "t4", "vendor": "Vendor B", "amount": 2000, "date": "2026-04-15"},
            {"id": "t5", "vendor": "Vendor C", "amount": 500, "date": "2026-04-20"},
            {"id": "t6", "vendor": "Vendor D", "amount": 500, "date": "2026-04-25"},
        ]
        # Vendor A = 8000/14000 ≈ 57%, Vendor B = 5000/14000 ≈ 36%
        findings = _analyze_concentration(transactions, threshold=0.30)
        assert len(findings) == 2

    def test_severity_critical_at_70_percent(self):
        transactions = [
            {"id": "t1", "vendor": "Big", "amount": 7500, "date": "2026-04-01"},
            {"id": "t2", "vendor": "Small", "amount": 2500, "date": "2026-04-01"},
        ]
        # Big = 75% → critical
        findings = _analyze_concentration(transactions, threshold=0.30)
        assert findings[0].severity == "critical"

    def test_severity_medium_at_40_percent(self):
        transactions = [
            {"id": "t1", "vendor": "Mid", "amount": 400, "date": "2026-04-01"},
            {"id": "t2", "vendor": "A", "amount": 200, "date": "2026-04-01"},
            {"id": "t3", "vendor": "B", "amount": 200, "date": "2026-04-01"},
            {"id": "t4", "vendor": "C", "amount": 200, "date": "2026-04-01"},
        ]
        # Mid = 400/1000 = 40% → medium
        findings = _analyze_concentration(transactions, threshold=0.30)
        assert len(findings) == 1
        assert findings[0].severity == "medium"

    def test_ignores_zero_and_negative_amounts(self):
        """Zero/negative amounts should be excluded; MegaVendor should not appear in findings."""
        transactions = [
            {"id": "t1", "vendor": "MegaVendor", "amount": 0, "date": "2026-04-01"},
            {"id": "t2", "vendor": "MegaVendor", "amount": -500, "date": "2026-04-02"},
            {"id": "t3", "vendor": "Other", "amount": 100, "date": "2026-04-03"},
        ]
        findings = _analyze_concentration(transactions, threshold=0.30)
        flagged_vendors = [f.metadata["vendor"] for f in findings]
        assert "MegaVendor" not in flagged_vendors

    def test_evidence_items_capped_at_five(self):
        transactions = [
            {"id": f"t{i}", "vendor": "BigVendor", "amount": 1000, "date": "2026-04-01"}
            for i in range(10)
        ] + [
            {"id": "other", "vendor": "Other", "amount": 100, "date": "2026-04-01"},
        ]
        findings = _analyze_concentration(transactions, threshold=0.30)
        assert len(findings) == 1
        assert len(findings[0].evidence) <= 5

    def test_recommended_next_steps_present(self):
        transactions = [
            {"id": "t1", "vendor": "V", "amount": 8000, "date": "2026-04-01"},
            {"id": "t2", "vendor": "Other", "amount": 2000, "date": "2026-04-01"},
        ]
        findings = _analyze_concentration(transactions, threshold=0.30)
        assert len(findings[0].recommended_next_steps) > 0

    def test_fixture_detects_megavendor_concentration(self):
        transactions = load_fixture_transactions()
        findings = _analyze_concentration(transactions, threshold=0.30)
        vendors = [f.metadata["vendor"] for f in findings]
        assert "MegaVendor Corp" in vendors

    def test_empty_transactions(self):
        findings = _analyze_concentration([], threshold=0.30)
        assert findings == []

    def test_metadata_totals_correct(self):
        """Both V (60%) and Other (40%) exceed the 30% threshold; verify V's metadata."""
        transactions = [
            {"id": "t1", "vendor": "V", "amount": 6000, "date": "2026-04-01"},
            {"id": "t2", "vendor": "Other", "amount": 4000, "date": "2026-04-01"},
        ]
        findings = _analyze_concentration(transactions, threshold=0.30)
        v_finding = next(f for f in findings if f.metadata["vendor"] == "V")
        assert v_finding.metadata["total_spend"] == pytest.approx(10000.0)
        assert v_finding.metadata["vendor_total"] == pytest.approx(6000.0)
        assert v_finding.metadata["concentration_pct"] == pytest.approx(0.60)
