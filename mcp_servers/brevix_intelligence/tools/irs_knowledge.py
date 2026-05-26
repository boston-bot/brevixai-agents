"""IRS Knowledge MCP tools — Phase 2 (not yet implemented).

These tools will provide structured IRS procedural intelligence:
- search_irm: Search the Internal Revenue Manual by topic
- explain_notice_type: Explain a specific IRS notice code
- summarize_collection_risk: Summarize risk for a given issue type
- recommend_records_to_gather: Recommend documentation for a given issue

See the architecture plan (docs/brevix_mcp_architecture_plan.md) for full design.
"""

from __future__ import annotations


def search_irm(topic: str) -> dict:
    raise NotImplementedError("IRS knowledge tools are planned for Phase 2.")


def explain_notice_type(notice_code: str) -> dict:
    raise NotImplementedError("IRS knowledge tools are planned for Phase 2.")


def summarize_collection_risk(issue_type: str) -> dict:
    raise NotImplementedError("IRS knowledge tools are planned for Phase 2.")


def recommend_records_to_gather(issue_type: str) -> dict:
    raise NotImplementedError("IRS knowledge tools are planned for Phase 2.")
