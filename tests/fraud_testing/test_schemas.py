"""Tests for fraud testing Pydantic schemas."""

import pytest

from app.fraud_testing.schemas import (
    FRAUD_CATEGORIES,
    DocumentRequest,
    ExpectedFinding,
    ExpectedIndicator,
    ExtractionImportPayload,
    FraudScenarioExtraction,
    InvestigationQuestion,
    MockCompany,
    MockDataImportPayload,
    MockParty,
    MockTransaction,
)


# ─── FraudScenarioExtraction ─────────────────────────────────────────────────


class TestFraudScenarioExtraction:
    def test_valid_extraction(self):
        e = FraudScenarioExtraction(
            scenario_title="Ghost Employee",
            fraud_category="Payroll Fraud",
            industry="Construction",
            primary_actor="Payroll Manager",
            concealment_methods=["Minimal employee records", "Relative bank account"],
            red_flags=["No personnel file", "Related party bank account"],
            records_needed=["Payroll register", "Personnel file"],
            investigation_questions=["Who approved this employee?"],
            summary="Payroll manager created a fictitious employee.",
            confidence_score=0.86,
        )
        assert e.fraud_category == "Payroll Fraud"
        assert e.confidence_score == 0.86

    def test_invalid_fraud_category_becomes_unknown(self):
        e = FraudScenarioExtraction(
            scenario_title="Test",
            fraud_category="Space Fraud",
            summary="Test",
            confidence_score=0.5,
        )
        assert e.fraud_category == "Unknown"

    def test_all_valid_fraud_categories_accepted(self):
        for cat in FRAUD_CATEGORIES:
            e = FraudScenarioExtraction(
                scenario_title="Test",
                fraud_category=cat,
                summary="Test",
                confidence_score=0.5,
            )
            assert e.fraud_category == cat

    def test_invalid_severity_becomes_none(self):
        e = FraudScenarioExtraction(
            scenario_title="Test",
            fraud_category="Unknown",
            severity="Catastrophic",
            summary="Test",
            confidence_score=0.5,
        )
        assert e.severity is None

    def test_valid_severity_accepted(self):
        e = FraudScenarioExtraction(
            scenario_title="Test",
            fraud_category="Unknown",
            severity="High",
            summary="Test",
            confidence_score=0.5,
        )
        assert e.severity == "High"


# ─── ExpectedIndicator ────────────────────────────────────────────────────────


class TestExpectedIndicator:
    def test_valid_indicator(self):
        ind = ExpectedIndicator(
            indicator_key="missing_personnel_file",
            indicator_name="Missing Personnel File",
            severity="High",
            should_detect=True,
        )
        assert ind.indicator_key == "missing_personnel_file"
        assert ind.should_detect is True

    def test_invalid_severity_raises(self):
        with pytest.raises(Exception):
            ExpectedIndicator(
                indicator_key="test",
                indicator_name="Test",
                severity="Extreme",
            )

    def test_defaults(self):
        ind = ExpectedIndicator(indicator_key="test", indicator_name="Test")
        assert ind.severity == "Medium"
        assert ind.should_detect is True
        assert ind.data_needed == []


# ─── ExpectedFinding ──────────────────────────────────────────────────────────


class TestExpectedFinding:
    def test_valid_finding(self):
        f = ExpectedFinding(
            finding_key="potential_ghost_employee",
            finding_title="Potential Ghost Employee",
            finding_description="Employee has no supporting records.",
            expected_risk_score=90,
            expected_confidence="High",
        )
        assert f.finding_key == "potential_ghost_employee"
        assert f.expected_risk_score == 90

    def test_risk_score_bounds(self):
        with pytest.raises(Exception):
            ExpectedFinding(
                finding_key="test",
                finding_title="Test",
                finding_description="Test",
                expected_risk_score=101,
            )

    def test_invalid_confidence_raises(self):
        with pytest.raises(Exception):
            ExpectedFinding(
                finding_key="test",
                finding_title="Test",
                finding_description="Test",
                expected_confidence="Very High",
            )


# ─── MockParty ────────────────────────────────────────────────────────────────


class TestMockParty:
    def test_valid_party(self):
        p = MockParty(
            external_party_id="EMP-001",
            party_type="Employee",
            party_name="Jane Smith",
        )
        assert p.is_fraud_actor is False
        assert p.is_related_party is False

    def test_invalid_party_type_becomes_unknown(self):
        p = MockParty(
            external_party_id="X-001",
            party_type="Robot",
            party_name="Bot",
        )
        assert p.party_type == "Unknown"

    def test_fraud_actor_flag(self):
        p = MockParty(
            external_party_id="GHOST-001",
            party_type="Employee",
            party_name="John Ghost",
            is_fraud_actor=True,
            is_related_party=True,
        )
        assert p.is_fraud_actor is True
        assert p.is_related_party is True


# ─── MockTransaction ──────────────────────────────────────────────────────────


class TestMockTransaction:
    def test_valid_transaction(self):
        tx = MockTransaction(
            external_transaction_id="TX-001",
            transaction_type="Payroll Payment",
            transaction_date="2025-01-15",
            amount=4500.00,
            external_party_id="EMP-001",
            is_fraudulent=False,
        )
        assert tx.amount == 4500.00
        assert tx.is_fraudulent is False

    def test_invalid_transaction_type_becomes_unknown(self):
        tx = MockTransaction(
            external_transaction_id="TX-001",
            transaction_type="Bribe",
            transaction_date="2025-01-15",
            amount=1000.00,
        )
        assert tx.transaction_type == "Unknown"

    def test_fraudulent_transaction(self):
        tx = MockTransaction(
            external_transaction_id="TX-FRAUD",
            transaction_type="Payroll Payment",
            transaction_date="2025-01-15",
            amount=3200.00,
            external_party_id="GHOST-001",
            is_fraudulent=True,
            fraud_pattern="ghost_employee",
            expected_brevix_signal="missing_personnel_file",
        )
        assert tx.is_fraudulent is True
        assert tx.fraud_pattern == "ghost_employee"


# ─── ExtractionImportPayload ──────────────────────────────────────────────────


class TestExtractionImportPayload:
    def _valid_payload(self) -> dict:
        return {
            "fraud_category": "Payroll Fraud",
            "industry": "Construction",
            "actor_type": "Payroll Manager",
            "summary": "Ghost employee scheme.",
            "confidence_score": 0.86,
            "model_name": "chatgpt-manual",
            "prompt_version": "fraud-extraction-v1",
            "structured_payload": {"scenario_title": "Ghost Employee"},
            "expected_indicators": [
                {
                    "indicator_key": "missing_personnel_file",
                    "indicator_name": "Missing Personnel File",
                    "severity": "High",
                }
            ],
            "expected_findings": [
                {
                    "finding_key": "potential_ghost_employee",
                    "finding_title": "Potential Ghost Employee",
                    "finding_description": "No supporting records.",
                    "expected_risk_score": 90,
                    "expected_confidence": "High",
                }
            ],
        }

    def test_valid_payload(self):
        payload = ExtractionImportPayload(**self._valid_payload())
        assert payload.fraud_category == "Payroll Fraud"
        assert len(payload.expected_indicators) == 1
        assert len(payload.expected_findings) == 1

    def test_to_api_dict(self):
        payload = ExtractionImportPayload(**self._valid_payload())
        d = payload.to_api_dict()
        assert isinstance(d["expected_indicators"], list)
        assert isinstance(d["expected_findings"], list)
        assert d["expected_indicators"][0]["indicator_key"] == "missing_personnel_file"

    def test_empty_lists_allowed(self):
        payload = ExtractionImportPayload(
            fraud_category="Unknown",
            structured_payload={},
        )
        assert payload.expected_indicators == []
        assert payload.expected_findings == []


# ─── MockDataImportPayload ────────────────────────────────────────────────────


class TestMockDataImportPayload:
    def _valid_payload(self) -> dict:
        return {
            "mock_company": {
                "company_name": "Acme Construction LLC",
                "industry": "Construction",
                "entity_type": "LLC",
                "employee_count": 20,
                "months_of_activity": 24,
            },
            "parties": [
                {"external_party_id": "EMP-001", "party_type": "Employee", "party_name": "Jane Smith"},
                {"external_party_id": "GHOST-001", "party_type": "Employee", "party_name": "John Ghost", "is_fraud_actor": True},
            ],
            "transactions": [
                {"external_transaction_id": "TX-001", "transaction_type": "Payroll Payment", "transaction_date": "2025-01-15", "amount": 4500.00, "external_party_id": "EMP-001"},
                {"external_transaction_id": "TX-002", "transaction_type": "Payroll Payment", "transaction_date": "2025-01-15", "amount": 3200.00, "external_party_id": "GHOST-001", "is_fraudulent": True},
            ],
        }

    def test_valid_payload(self):
        payload = MockDataImportPayload(**self._valid_payload())
        assert payload.mock_company.company_name == "Acme Construction LLC"
        assert len(payload.parties) == 2
        assert len(payload.transactions) == 2

    def test_to_api_dict(self):
        payload = MockDataImportPayload(**self._valid_payload())
        d = payload.to_api_dict()
        assert d["mock_company"]["company_name"] == "Acme Construction LLC"
        assert len(d["parties"]) == 2
        assert len(d["transactions"]) == 2

    def test_missing_company_raises(self):
        with pytest.raises(Exception):
            MockDataImportPayload(parties=[], transactions=[])
