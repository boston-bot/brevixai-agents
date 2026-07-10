from __future__ import annotations

import pytest

from app.playbook_retrieval import retrieve_playbook_context


class PlaybookClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def fraud_playbook_search(
        self,
        query: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.calls.append({
            "query": query,
            "limit": limit,
            "user_id": user_id,
            "trace_id": trace_id,
            "trace_metadata": trace_metadata,
        })
        return {
            "corpus_version": "fraud_playbooks:v2",
            "results": [
                {
                    "source_id": "12",
                    "title": "Duplicate invoice payment review",
                    "confidence": "high",
                    "relevance_score": 0.91,
                    "document": {
                        "source_id": "12",
                        "title": "Duplicate invoice payment review",
                        "tests": ["Match invoice numbers across payment batches"],
                        "document_requests": ["Vendor invoice copies"],
                        "red_flags": ["Manual payment recorded outside the approval flow"],
                    },
                    "citations": [{"fields": ["tests", "red_flags"]}],
                },
                {
                    "source_id": "99",
                    "title": "Low confidence review",
                    "confidence": "low",
                    "relevance_score": 0.2,
                    "document": {
                        "source_id": "99",
                        "title": "Low confidence review",
                        "tests": ["Should not be included"],
                        "document_requests": ["Should not be requested"],
                        "red_flags": ["Should not be surfaced"],
                    },
                },
            ],
            "disclaimer": "Playbook guidance supports human review only.",
        }


@pytest.mark.asyncio
async def test_retrieve_playbook_context_extracts_review_guidance() -> None:
    client = PlaybookClient()

    context = await retrieve_playbook_context(
        client,
        {
            "user_message": "Review duplicate invoice payments.",
            "user_id": "user-1",
            "agent_run_id": "run-1",
            "intent": "fraud_pattern_search",
        },
    )

    assert client.calls == [
        {
            "query": "Review duplicate invoice payments.",
            "limit": 5,
            "user_id": "user-1",
            "trace_id": "run-1",
            "trace_metadata": {"intent": "fraud_pattern_search"},
        }
    ]
    assert context["status"] == "matched"
    assert context["corpus_version"] == "fraud_playbooks:v2"
    assert context["playbook_refs"] == [
        {
            "playbook_id": "12",
            "title": "Duplicate invoice payment review",
            "confidence": "high",
            "relevance_score": 0.91,
            "corpus_version": "fraud_playbooks:v2",
            "matched_fields": ["tests", "red_flags"],
        }
    ]
    assert context["recommended_tests"] == ["Match invoice numbers across payment batches"]
    assert context["document_requests"] == ["Vendor invoice copies"]
    assert context["red_flags"] == ["Manual payment recorded outside the approval flow"]
    assert context["evidence_requests"] == [
        {
            "requirement_key": "playbook_vendor_invoice_copies",
            "label": "Vendor invoice copies",
            "reason": (
                "Requested by the matched review playbook 'Duplicate invoice payment review' "
                "to support evidence review."
            ),
            "priority": "recommended",
            "status": "missing",
            "source": "fraud_playbook",
            "playbook_id": "12",
        }
    ]
    assert context["disclaimer"] == "Playbook guidance supports human review only."


@pytest.mark.asyncio
async def test_retrieve_playbook_context_includes_available_company_context() -> None:
    client = PlaybookClient()

    await retrieve_playbook_context(
        client,
        {
            "user_message": "Review this payment.",
            "user_id": "user-1",
            "agent_run_id": "run-1",
            "intent": "fraud_pattern_search",
            "page_context": {
                "vendor_name": "Northstar Consulting",
                "invoice_number": "INV-100",
            },
            "company_context": {
                "transaction_summary": {
                    "transactions": [
                        {
                            "vendor": "Northstar Consulting",
                            "invoice_number": "INV-100",
                            "memo": "April services",
                            "category": "Consulting",
                        }
                    ],
                },
            },
        },
    )

    query = client.calls[0]["query"]
    assert query.startswith("Review this payment.\nContext: ")
    assert "vendor name: Northstar Consulting" in query
    assert "invoice number: INV-100" in query
    assert "memo: April services" in query
    assert "category: Consulting" in query
