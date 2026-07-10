from __future__ import annotations


class FakeLaravelToolClient:
    def __init__(self) -> None:
        self.risk_summary_calls: list[dict] = []
        self.company_context_calls: list[dict] = []
        self.vendor_risk_calls: list[dict] = []
        self.reconciliation_risk_calls: list[dict] = []
        self.entity_relationship_risk_calls: list[dict] = []
        self.aggregate_risk_summary_calls: list[dict] = []
        self.alert_recommendations_calls: list[dict] = []
        self.case_recommendations_calls: list[dict] = []
        self.pending_recommendations_calls: list[dict] = []
        self.dashboard_health_calls: list[dict] = []
        self.transaction_lookup_calls: list[dict] = []
        self.transaction_detail_calls: list[dict] = []
        self.process_registry_calls: list[dict] = []
        self.irm_search_calls: list[dict] = []
        self.irm_section_calls: list[dict] = []
        self.irs_notice_type_calls: list[dict] = []
        self.irs_records_checklist_calls: list[dict] = []
        self.irs_collection_risk_calls: list[dict] = []
        self.irs_notice_extract_calls: list[dict] = []
        self.fraud_playbook_search_calls: list[dict] = []
        self.fraud_playbook_feedback_calls: list[dict] = []

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

    async def alert_recommendations(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.alert_recommendations_calls.append({"company_id": company_id, "user_id": user_id})
        return {"company_id": company_id, "pending_count": 0, "recommendations": []}

    async def case_recommendations(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.case_recommendations_calls.append({"company_id": company_id, "user_id": user_id})
        return {"company_id": company_id, "pending_count": 0, "recommendations": []}

    async def pending_recommendations(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.pending_recommendations_calls.append({"company_id": company_id, "user_id": user_id})
        return {
            "company_id": company_id,
            "alert_recommendations": {"pending_count": 0, "recommendations": []},
            "case_recommendations": {"pending_count": 0, "recommendations": []},
        }

    async def dashboard_health(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.dashboard_health_calls.append({"company_id": company_id, "user_id": user_id})
        return {
            "company_id": company_id,
            "risk_score": 42,
            "total_transactions": 128,
            "flagged_alerts": 3,
            "vendors_monitored": 18,
            "amount_reviewed": 125000.75,
        }

    async def transaction_lookup(
        self,
        company_id: str,
        user_id: str,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int | None = None,
        vendor: str | None = None,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.transaction_lookup_calls.append({"company_id": company_id, "user_id": user_id})
        return {"company_id": company_id, "total": 0, "returned_count": 0, "transactions": []}

    async def transaction_detail(
        self,
        company_id: str,
        user_id: str,
        ids: list[str] | None = None,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.transaction_detail_calls.append({"company_id": company_id, "user_id": user_id, "ids": ids})
        return {"company_id": company_id, "requested_count": len(ids or []), "found_count": 0, "transactions": []}

    async def behavioral_baseline(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        return {
            "deviation_score": 0,
            "risk_level": "info",
            "anomalies": [],
            "baseline": {
                "avg_weekly_spend": 0.0,
                "avg_vendor_count": 0.0,
                "top_categories": [],
                "payment_frequency_distribution": {},
                "baseline_period_days": 90,
                "transaction_count": 0,
            },
            "current": {},
        }

    async def onboarding_context(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        return {
            "company_id": company_id,
            "session_status": "not_started",
            "primary_intent": None,
            "current_step": None,
            "scope_mode": None,
        }

    async def evidence_requirements(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        return {"company_id": company_id, "items": []}

    async def data_source_status(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        return {"company_id": company_id, "sources": [], "total_sources": 0}

    async def first_snapshot(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        return {
            "company_id": company_id,
            "data_readiness_score": 0,
            "review_scope": "none",
            "available_sources": [],
            "missing_evidence": [],
            "risk_indicators": [],
            "data_quality_issues": [],
            "recommended_next_action": None,
        }

    async def action_plan(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        return {"company_id": company_id, "current_objective": None, "next_best_action": None}

    async def process_registry(
        self,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.process_registry_calls.append({"user_id": user_id})
        return {"processes": [], "action_types": []}

    async def irm_search(
        self,
        topic: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.irm_search_calls.append({"topic": topic, "limit": limit, "user_id": user_id})
        return {
            "status": "ok",
            "query": topic,
            "results": [
                {
                    "irm_reference": "5.11.1.1",
                    "title": "Levy authority",
                    "summary": "The returned IRM section describes procedural collection activity.",
                }
            ],
        }

    async def irm_section(
        self,
        reference: str,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.irm_section_calls.append({"reference": reference, "user_id": user_id})
        return {
            "status": "ok",
            "reference": reference,
            "result": {
                "irm_reference": reference,
                "title": "Requested IRM section",
                "summary": "The requested IRM section was returned by exact reference lookup.",
            },
        }

    async def irs_notice_type(
        self,
        code: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.irs_notice_type_calls.append({"code": code, "limit": limit, "user_id": user_id})
        return {
            "status": "ok",
            "notice_code": code,
            "results": [
                {
                    "irm_reference": "5.19.1.6",
                    "title": f"{code} notice procedures",
                    "summary": "The returned IRM-backed result explains the notice procedure.",
                }
            ],
        }

    async def irs_records_checklist(
        self,
        issue_type: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.irs_records_checklist_calls.append({"issue_type": issue_type, "limit": limit, "user_id": user_id})
        return {
            "status": "ok",
            "issue_type": issue_type,
            "recommended_records": ["IRS notice", "account transcript", "payment records"],
            "results": [
                {
                    "irm_reference": "5.1.10.3",
                    "title": "Collection case documentation",
                    "summary": "The returned result identifies records that support collection-procedure review.",
                }
            ],
        }

    async def irs_collection_risk(
        self,
        issue_type: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.irs_collection_risk_calls.append({"issue_type": issue_type, "limit": limit, "user_id": user_id})
        return {
            "status": "ok",
            "issue_type": issue_type,
            "results": [
                {
                    "irm_reference": "5.11.1.1",
                    "title": "Collection process",
                    "summary": "The returned IRM-backed result describes IRS collection procedure.",
                }
            ],
        }

    async def irs_notice_extract(
        self,
        text: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.irs_notice_extract_calls.append({"text": text, "limit": limit, "user_id": user_id})
        return {
            "status": "ok",
            "notice_type": "CP504",
            "deadline_days": 30,
            "deadline_description": "30-day window from notice date",
            "required_action": "Pay in full or file Form 9465 to stop levy action.",
            "risk_level": "critical",
            "key_amount": 5000.0,
            "summary": "CP504 is an urgent notice of intent to levy state tax refunds.",
            "irm_search_topic": "levy notice intent to levy balance due collection",
            "results": [
                {
                    "irm_reference": "5.11.1.1",
                    "title": "Notice of Levy",
                    "summary": "The returned IRM-backed result describes the levy notice procedure.",
                }
            ],
            "disclaimer": "For informational purposes only.",
        }

    async def fraud_playbook_search(
        self,
        query: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.fraud_playbook_search_calls.append({"query": query, "limit": limit, "user_id": user_id})
        documents = [
            {
                "id": 12,
                "source_id": "12",
                "title": "Duplicate invoice payment review",
                "category": "vendor_payments",
                "description": "Review pattern for repeated payments recorded against a single invoice.",
                "symptoms": ["Same invoice number paid more than once", "Matching payment amounts days apart"],
                "red_flags": ["Vendor with duplicate remit-to accounts", "Manual payment recorded outside the approval flow"],
                "tests": ["Match invoice numbers across payment batches", "Compare payment dates for identical amounts"],
                "document_requests": ["Vendor invoice copies", "Payment approval records"],
                "intent_key": "duplicate_payment_review",
                "is_active": True,
            },
            {
                "id": 31,
                "source_id": "31",
                "title": "Vendor master change review",
                "category": "vendor_payments",
                "description": "Review pattern for unverified vendor master data changes before payment.",
                "symptoms": ["Bank details changed shortly before a payment run"],
                "red_flags": ["Vendor bank change without a documented callback verification"],
                "tests": ["Trace vendor bank changes to an approved change request"],
                "document_requests": ["Vendor change history export"],
                "intent_key": "vendor_master_change_review",
                "is_active": True,
            },
        ]
        return {
            "status": "ok",
            "corpus_id": "fraud_playbooks",
            "corpus_version": "fraud_playbooks:v2",
            "query": query,
            "result_count": 2,
            "scoring": {"strategy": "lexical_playbook_v2", "hybrid": False},
            "results": [
                {
                    "source_type": "fraud_playbook",
                    "source_id": "12",
                    "title": "Duplicate invoice payment review",
                    "snippet": "Same invoice number paid more than once.",
                    "snippet_field": "symptoms",
                    "relevance_score": 0.91,
                    "confidence": "high",
                    "score_components": {"term_overlap": 0.8, "field_weight": 0.11},
                    "document": documents[0],
                    "citations": [
                        {
                            "source_type": "fraud_playbook",
                            "source_id": "12",
                            "title": "Duplicate invoice payment review",
                            "source_name": "fraud_playbooks",
                            "source_version": "fraud_playbooks:v2",
                            "fields": ["symptoms", "tests"],
                        }
                    ],
                },
                {
                    "source_type": "fraud_playbook",
                    "source_id": "31",
                    "title": "Vendor master change review",
                    "snippet": "Bank details changed shortly before a payment run.",
                    "snippet_field": "red_flags",
                    "relevance_score": 0.62,
                    "confidence": "medium",
                    "score_components": {"term_overlap": 0.5, "field_weight": 0.12},
                    "document": documents[1],
                    "citations": [
                        {
                            "source_type": "fraud_playbook",
                            "source_id": "31",
                            "title": "Vendor master change review",
                            "source_name": "fraud_playbooks",
                            "source_version": "fraud_playbooks:v2",
                            "fields": ["red_flags"],
                        }
                    ],
                },
            ],
            "citations": [
                {
                    "source_type": "fraud_playbook",
                    "source_id": "12",
                    "title": "Duplicate invoice payment review",
                    "source_name": "fraud_playbooks",
                    "source_version": "fraud_playbooks:v2",
                    "fields": ["symptoms", "tests"],
                },
                {
                    "source_type": "fraud_playbook",
                    "source_id": "31",
                    "title": "Vendor master change review",
                    "source_name": "fraud_playbooks",
                    "source_version": "fraud_playbooks:v2",
                    "fields": ["red_flags"],
                },
            ],
            "metadata": {
                "terms": ["duplicate", "invoice", "vendor"],
                "expanded_terms": ["duplicate", "invoice", "vendor", "payment"],
                "retrieval_stage": "lexical",
                "feedback_boost_applied": False,
            },
            "disclaimer": (
                "Playbook guidance is informational and supports human review only. "
                "It does not conclude that any improper activity occurred and is not "
                "legal, tax, or accounting advice."
            ),
            "data": documents,
        }

    async def fraud_playbook_feedback(
        self,
        playbook_id: int,
        query_text: str,
        relevance_score: int,
        user_feedback: str | None = None,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.fraud_playbook_feedback_calls.append({
            "playbook_id": playbook_id,
            "query_text": query_text,
            "relevance_score": relevance_score,
            "user_feedback": user_feedback,
            "user_id": user_id,
        })
        return {
            "message": "Playbook feedback recorded.",
            "data": {
                "playbook_id": playbook_id,
                "query_text": query_text,
                "relevance_score": relevance_score,
                "user_feedback": user_feedback,
            },
            "disclaimer": "For informational purposes only.",
        }


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

    async def alert_recommendations(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("alert_recommendations", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def case_recommendations(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("case_recommendations", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def pending_recommendations(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("pending_recommendations", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def dashboard_health(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("dashboard_health", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def transaction_lookup(
        self,
        company_id: str,
        user_id: str,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int | None = None,
        vendor: str | None = None,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("transaction_lookup", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def transaction_detail(
        self,
        company_id: str,
        user_id: str,
        ids: list[str] | None = None,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("transaction_detail", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def behavioral_baseline(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("behavioral_baseline", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def onboarding_context(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("onboarding_context", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def evidence_requirements(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("evidence_requirements", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def data_source_status(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("data_source_status", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def first_snapshot(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("first_snapshot", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def action_plan(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("action_plan", {})
        return {"company_id": company_id, **fixture} if isinstance(fixture, dict) else {}

    async def process_registry(
        self,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        return self.risk_fixture.get("process_registry", {"processes": [], "action_types": []})

    async def irm_search(
        self,
        topic: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("irm_search", {})
        return {"status": "ok", "query": topic, **fixture} if isinstance(fixture, dict) else {}

    async def irm_section(
        self,
        reference: str,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("irm_section", {})
        return {"status": "ok", "reference": reference, **fixture} if isinstance(fixture, dict) else {}

    async def irs_notice_type(
        self,
        code: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("irs_notice_type", {})
        return {"status": "ok", "notice_code": code, **fixture} if isinstance(fixture, dict) else {}

    async def irs_records_checklist(
        self,
        issue_type: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("irs_records_checklist", {})
        return {"status": "ok", "issue_type": issue_type, **fixture} if isinstance(fixture, dict) else {}

    async def irs_collection_risk(
        self,
        issue_type: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("irs_collection_risk", {})
        return {"status": "ok", "issue_type": issue_type, **fixture} if isinstance(fixture, dict) else {}

    async def irs_notice_extract(
        self,
        text: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("irs_notice_extract", {})
        return {"status": "ok", **fixture} if isinstance(fixture, dict) else {}

    async def fraud_playbook_search(
        self,
        query: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("fraud_playbook_search", {})
        return {"status": "no_results", "query": query, "results": [], **fixture} if isinstance(fixture, dict) else {}

    async def fraud_playbook_feedback(
        self,
        playbook_id: int,
        query_text: str,
        relevance_score: int,
        user_feedback: str | None = None,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        fixture = self.risk_fixture.get("fraud_playbook_feedback", {})
        return {"message": "Playbook feedback recorded.", **fixture} if isinstance(fixture, dict) else {}


def base_state(message: str = "Are there any suspicious vendors this month?") -> dict:
    return {
        "company_id": "company-1",
        "user_id": "user-1",
        "agent_run_id": "agent-run-1",
        "user_message": message,
        "page_context": {"selected_period": "2026-05", "source": "test"},
        "conversation_history": None,
        "tool_results": {},
        "alert_recommendations": None,
        "case_recommendations": None,
        "pending_recommendations": None,
        "dashboard_health": None,
        "behavioral_baseline": None,
        "selected_tools": None,
        "findings": [],
        "investigative_synthesis": {},
        "recommended_actions": [],
        "irs_answer": None,
        "errors": [],
        "steps": [],
        "playbook_refs": [],
        "retrieval_query": None,
    }
