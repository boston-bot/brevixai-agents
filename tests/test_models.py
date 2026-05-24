from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import AgentRunRequest


def test_agent_run_request_accepts_numeric_laravel_ids() -> None:
    request = AgentRunRequest.model_validate(
        {
            "agent_run_id": 789,
            "company_id": 123,
            "user_id": 456,
            "conversation_id": 101112,
            "message": "Are there any suspicious vendors this month?",
            "page_context": None,
        }
    )

    assert request.agent_run_id == "789"
    assert request.company_id == "123"
    assert request.user_id == "456"
    assert request.conversation_id == "101112"
    assert request.page_context == {}


def test_agent_run_request_accepts_legacy_content_key() -> None:
    request = AgentRunRequest.model_validate(
        {
            "company_id": "company-123",
            "user_id": "user-456",
            "content": "Are there duplicate invoice risks?",
        }
    )

    assert request.message == "Are there duplicate invoice risks?"


def test_agent_run_request_accepts_chatgpt_messages_payload() -> None:
    request = AgentRunRequest.model_validate(
        {
            "company_id": "company-123",
            "user_id": "user-456",
            "messages": [
                {"role": "system", "content": "You are Rex."},
                {"role": "user", "content": "  Check risky vendors  "},
            ],
        }
    )

    assert request.message == "Check risky vendors"


def test_agent_run_request_accepts_message_content_parts() -> None:
    request = AgentRunRequest.model_validate(
        {
            "company_id": "company-123",
            "user_id": "user-456",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Check May"},
                        {"type": "text", "text": "duplicate invoices"},
                    ],
                }
            ],
        }
    )

    assert request.message == "Check May\nduplicate invoices"


def test_agent_run_request_accepts_responses_api_input_string() -> None:
    request = AgentRunRequest.model_validate(
        {
            "company_id": "company-123",
            "user_id": "user-456",
            "input": "Summarize reconciliation mismatches",
        }
    )

    assert request.message == "Summarize reconciliation mismatches"


def test_agent_run_request_accepts_empty_list_page_context_from_laravel() -> None:
    request = AgentRunRequest.model_validate(
        {
            "company_id": "company-123",
            "user_id": "user-456",
            "message": "Are there duplicate invoice risks?",
            "page_context": [],
        }
    )

    assert request.page_context == {}


def test_agent_run_request_rejects_boolean_ids() -> None:
    with pytest.raises(ValidationError):
        AgentRunRequest.model_validate(
            {
                "company_id": True,
                "user_id": 456,
                "message": "Are there any suspicious vendors this month?",
            }
        )


def test_agent_run_request_rejects_whitespace_message() -> None:
    with pytest.raises(ValidationError, match="non-whitespace"):
        AgentRunRequest.model_validate(
            {
                "company_id": "company-123",
                "user_id": "user-456",
                "message": "   ",
            }
        )
