from __future__ import annotations


class FakeLaravelToolClient:
    def __init__(self) -> None:
        self.risk_summary_calls: list[dict] = []
        self.company_context_calls: list[dict] = []
        self.vendor_risk_calls: list[dict] = []
        self.reconciliation_risk_calls: list[dict] = []
        self.entity_relationship_risk_calls: list[dict] = []
        self.aggregate_risk_summary_calls: list[dict] = []

    async def company_context(
        self,
        company_id: str,
        user_id: str,
        dashboard_context: bool = False,
        transaction_filters: dict | None = None,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.company_context_calls.append({
            "company_id": company_id,
            "user_id": user_id,
            "dashboard_context": dashboard_context,
            "transaction_filters": transaction_filters,
        })

        context = {
            "company_id": company_id,
            "company_name": "Brevix Test Co",
            "industry": "Retail",
            "available_data_sources": ["file_upload"],
            "user_role": "owner",
        }
        if transaction_filters is not None:
            context["transaction_summary"] = {
                "date_from": transaction_filters.get("date_from"),
                "date_to": transaction_filters.get("date_to"),
                "total": 2,
                "returned_count": 2,
                "transactions": [
                    {
                        "id": "txn-1",
                        "date": "2026-05-18",
                        "vendor": "Acme Supplies",
                        "amount": 125.5,
                        "type": "expense",
                        "category": "Office Supplies",
                        "status": "completed",
                    },
                    {
                        "id": "txn-2",
                        "date": "2026-05-17",
                        "vendor": "Northstar Consulting",
                        "amount": 2500.0,
                        "type": "expense",
                        "category": "Consulting",
                        "status": "flagged",
                    },
                ],
            }

        if dashboard_context:
            context["dashboard_summary"] = {
                "risk_score": 42,
                "total_transactions": 128,
                "flagged_alerts": 3,
                "vendors_monitored": 18,
                "amount_reviewed": 125000.75,
            }

        return context

    async def risk_summary(
        self,
        company_id: str,
        user_id: str,
        period: str | None = None,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.risk_summary_calls.append({"company_id": company_id, "user_id": user_id, "period": period})

        return {
            "company_id": company_id,
            "risk_score": 74,
            "risk_level": "high",
            "period": period or "2026-05",
            "top_drivers": [
                {
                    "driver": "Possible unusual vendor pattern",
                    "description": "Open alerts are driving the risk score.",
                    "severity": "medium",
                    "evidence": [{"type": "alert", "id": "alert-1"}],
                }
            ],
        }

    async def vendor_risk(
        self,
        company_id: str,
        user_id: str,
        vendor: str | None = None,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.vendor_risk_calls.append({"company_id": company_id, "user_id": user_id, "vendor": vendor})
        return {}

    async def reconciliation_risk(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.reconciliation_risk_calls.append({"company_id": company_id, "user_id": user_id})
        return {}

    async def entity_relationship_risk(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.entity_relationship_risk_calls.append({"company_id": company_id, "user_id": user_id})
        return {}

    async def aggregate_risk_summary(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.aggregate_risk_summary_calls.append({"company_id": company_id, "user_id": user_id})
        return {}


class FixtureLaravelToolClient:
    """Fake tool client that returns a caller-supplied risk fixture for evaluation runs."""

    def __init__(self, risk_fixture: dict) -> None:
        self.risk_fixture = risk_fixture
        self.risk_summary_calls: list[dict] = []

    async def company_context(
        self,
        company_id: str,
        user_id: str,
        dashboard_context: bool = False,
        transaction_filters: dict | None = None,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        return {
            "company_id": company_id,
            "company_name": "Brevix Eval Co",
            "industry": "Retail",
            "available_data_sources": ["file_upload"],
            "user_role": "owner",
        }

    async def risk_summary(
        self,
        company_id: str,
        user_id: str,
        period: str | None = None,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.risk_summary_calls.append({"company_id": company_id, "user_id": user_id, "period": period})
        fixture = self.risk_fixture.get("risk_summary", self.risk_fixture)
        return {"company_id": company_id, **fixture}

    async def vendor_risk(
        self,
        company_id: str,
        user_id: str,
        vendor: str | None = None,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("vendor_risk", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def reconciliation_risk(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("reconciliation_risk", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def entity_relationship_risk(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("entity_relationship_risk", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def aggregate_risk_summary(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("aggregate_risk_summary", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}


def base_state(message: str = "Are there any suspicious vendors this month?") -> dict:
    return {
        "company_id": "company-1",
        "user_id": "user-1",
        "agent_run_id": "agent-run-1",
        "user_message": message,
        "page_context": {"selected_period": "2026-05", "source": "test"},
        "tool_results": {},
        "findings": [],
        "investigative_synthesis": {},
        "recommended_actions": [],
        "errors": [],
        "steps": [],
    }
