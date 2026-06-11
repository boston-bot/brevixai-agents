"""Pydantic schemas for the Brevix fraud testing pipeline.

These schemas define the contract between ChatGPT-generated JSON and
the brevixai-api import endpoints. They are used for validation before
import and as reference for prompt engineering.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FRAUD_CATEGORIES = [
    "Payroll Fraud",
    "Vendor Fraud",
    "Shell Vendor Fraud",
    "Expense Reimbursement Fraud",
    "Revenue Manipulation",
    "Inventory Theft",
    "Tax Risk",
    "Internal Control Failure",
    "Waste or Abuse",
    "Bookkeeping Error",
    "Mixed Fraud",
    "Unknown",
]

SEVERITY_VALUES = ["Low", "Medium", "High", "Critical"]
PRIORITY_VALUES = ["Low", "Medium", "High", "Critical"]
CONFIDENCE_VALUES = ["Low", "Medium", "High"]

PARTY_TYPES = [
    "Employee",
    "Vendor",
    "Customer",
    "Owner",
    "Bookkeeper",
    "Payroll Manager",
    "AP Clerk",
    "Related Party",
    "Unknown",
]

TRANSACTION_TYPES = [
    "Bill",
    "Bill Payment",
    "Invoice",
    "Payment",
    "Journal Entry",
    "Payroll Payment",
    "Expense",
    "Check",
    "Credit Card Charge",
    "Vendor Credit",
    "Customer Refund",
    "Deposit",
    "Owner Draw",
]


# ─── Extraction sub-schemas ───────────────────────────────────────────────────


class ExpectedIndicator(BaseModel):
    indicator_key: str = Field(..., description="snake_case key, e.g. missing_personnel_file")
    indicator_name: str
    indicator_category: str = ""
    description: str = ""
    severity: str = "Medium"
    data_needed: list[str] = Field(default_factory=list)
    should_detect: bool = True

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        if v not in SEVERITY_VALUES:
            raise ValueError(f"severity must be one of {SEVERITY_VALUES}, got '{v}'")
        return v


class ExpectedFinding(BaseModel):
    finding_key: str = Field(..., description="snake_case key, e.g. potential_ghost_employee")
    finding_title: str
    finding_description: str
    expected_risk_score: int = Field(default=50, ge=0, le=100)
    expected_confidence: str = "Medium"
    recommended_action: str = ""
    expected_user_message: str = ""

    @field_validator("expected_confidence")
    @classmethod
    def validate_confidence(cls, v: str) -> str:
        if v not in CONFIDENCE_VALUES:
            raise ValueError(f"expected_confidence must be one of {CONFIDENCE_VALUES}, got '{v}'")
        return v


class DocumentRequest(BaseModel):
    document_name: str
    why_needed: str = ""
    priority: str = "Medium"
    expected_issue_found: str | None = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in PRIORITY_VALUES:
            raise ValueError(f"priority must be one of {PRIORITY_VALUES}, got '{v}'")
        return v


class InvestigationQuestion(BaseModel):
    question: str
    asked_to: str = ""
    why_question_matters: str = ""
    priority: str = "Medium"

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in PRIORITY_VALUES:
            raise ValueError(f"priority must be one of {PRIORITY_VALUES}, got '{v}'")
        return v


# ─── Main extraction schema ───────────────────────────────────────────────────


class FraudScenarioExtraction(BaseModel):
    """Structured extraction of a fraud narrative — output of the ChatGPT prompt."""

    scenario_title: str
    fraud_category: str
    industry: str | None = None
    primary_actor: str | None = None
    secondary_actors: list[str] = Field(default_factory=list)
    victim_entity: str | None = None
    concealment_methods: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    records_needed: list[str] = Field(default_factory=list)
    investigation_questions_text: list[str] = Field(
        default_factory=list,
        alias="investigation_questions",
        description="Plain-text questions. Use investigation_question_objects for structured form.",
    )
    estimated_loss: float | None = None
    severity: str | None = None
    summary: str
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("fraud_category")
    @classmethod
    def validate_fraud_category(cls, v: str) -> str:
        if v not in FRAUD_CATEGORIES:
            return "Unknown"
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str | None) -> str | None:
        if v is not None and v not in SEVERITY_VALUES:
            return None
        return v

    model_config = ConfigDict(populate_by_name=True)


# ─── Mock data schemas ────────────────────────────────────────────────────────


class MockParty(BaseModel):
    external_party_id: str = Field(..., description="Stable ID used to reference this party in transactions")
    party_type: str
    party_name: str
    role: str | None = None
    is_fraud_actor: bool = False
    is_related_party: bool = False
    attributes: dict = Field(default_factory=dict)

    @field_validator("party_type")
    @classmethod
    def validate_party_type(cls, v: str) -> str:
        if v not in PARTY_TYPES:
            return "Unknown"
        return v


class MockTransaction(BaseModel):
    external_transaction_id: str
    transaction_type: str
    transaction_date: str = Field(..., description="ISO date string YYYY-MM-DD")
    amount: float
    external_party_id: str | None = None
    account_category: str = ""
    description: str = ""
    is_fraudulent: bool = False
    fraud_pattern: str | None = None
    expected_brevix_signal: str | None = None
    payload: dict = Field(default_factory=dict)

    @field_validator("transaction_type")
    @classmethod
    def validate_transaction_type(cls, v: str) -> str:
        if v not in TRANSACTION_TYPES:
            return "Unknown"
        return v


class MockCompany(BaseModel):
    company_name: str
    industry: str = ""
    entity_type: str = ""
    annual_revenue: float = 0.0
    employee_count: int = 0
    vendor_count: int = 0
    customer_count: int = 0
    months_of_activity: int = 12
    normal_business_behavior: str = ""


# ─── Top-level import payloads ────────────────────────────────────────────────


class ExtractionImportPayload(BaseModel):
    """Full extraction payload sent to POST /api/internal/fraud-scenarios/{id}/extraction."""

    fraud_category: str
    industry: str | None = None
    actor_type: str | None = None
    concealment_method: str | None = None
    summary: str | None = None
    confidence_score: float | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    structured_payload: dict = Field(default_factory=dict)
    expected_indicators: list[ExpectedIndicator] = Field(default_factory=list)
    expected_findings: list[ExpectedFinding] = Field(default_factory=list)
    document_requests: list[DocumentRequest] = Field(default_factory=list)
    investigation_questions: list[InvestigationQuestion] = Field(default_factory=list)

    def to_api_dict(self) -> dict:
        d = self.model_dump()
        d["expected_indicators"] = [i.model_dump() for i in self.expected_indicators]
        d["expected_findings"] = [f.model_dump() for f in self.expected_findings]
        d["document_requests"] = [r.model_dump() for r in self.document_requests]
        d["investigation_questions"] = [q.model_dump() for q in self.investigation_questions]
        return d


class MockDataImportPayload(BaseModel):
    """Full mock data payload sent to POST /api/internal/fraud-scenarios/{id}/mock-data."""

    mock_company: MockCompany
    parties: list[MockParty] = Field(default_factory=list)
    transactions: list[MockTransaction] = Field(default_factory=list)
    generation_metadata: dict = Field(default_factory=dict)

    def to_api_dict(self) -> dict:
        return {
            "mock_company": self.mock_company.model_dump(),
            "parties": [p.model_dump() for p in self.parties],
            "transactions": [t.model_dump() for t in self.transactions],
            "generation_metadata": self.generation_metadata,
        }
