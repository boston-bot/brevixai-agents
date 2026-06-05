from __future__ import annotations

from app.relational_graph_projection import (
    build_relational_graph_projection,
    synthesize_relational_graph_projection_answer,
)


def _ready_sources() -> dict:
    return {
        "company_context": {
            "company_id": "company-1",
            "company_name": "Brevix Test Co",
            "user_id": "user-1",
            "user_role": "owner",
        },
        "transactions": [
            {
                "id": "txn-1",
                "company_id": "company-1",
                "company_user_id": "user-1",
                "vendor_id": "vendor-1",
                "vendor": "ABC Supply",
                "bank_account_id": "bank-1",
                "approved_by": "employee-1",
                "document_id": "doc-1",
                "amount": 1000.0,
                "date": "2026-05-01",
            },
            {
                "id": "txn-2",
                "company_id": "company-1",
                "company_user_id": "user-1",
                "vendor_id": "vendor-2",
                "vendor": "XYZ Supply",
                "bank_account_id": "bank-1",
                "approved_by": "employee-1",
                "document_id": "doc-2",
                "amount": 850.0,
                "date": "2026-05-02",
            },
        ],
        "vendor_risk": {
            "vendors": [
                {"vendor_id": "vendor-1", "vendor_name": "ABC Supply", "vendor_risk_score": 72},
                {"vendor_id": "vendor-2", "vendor_name": "XYZ Supply", "vendor_risk_score": 58},
            ]
        },
        "entity_relationship_risk": {
            "supporting_evidence": [
                {
                    "id": "rel-1",
                    "employee_id": "employee-1",
                    "vendor_id": "vendor-1",
                    "bank_account_id": "bank-1",
                    "related_vendor_id": "vendor-2",
                    "relationship_type": "shared_address",
                }
            ]
        },
    }


def test_relational_graph_projection_blocks_until_readiness_audit_passes() -> None:
    projection = build_relational_graph_projection(
        {
            "transactions": [
                {"id": "txn-1", "vendor": "ABC Supply", "amount": 1000.0, "date": "2026-05-01"}
            ]
        }
    )

    assert projection["status"] == "blocked"
    assert projection["phase_5_ready"] is False
    assert projection["nodes"] == []
    assert projection["edges"] == []
    assert projection["critical_blockers"]
    assert projection["recommended_action"]["type"] == "prepare_relational_data_contracts"


def test_relational_graph_projection_builds_nodes_and_core_edges() -> None:
    projection = build_relational_graph_projection(_ready_sources())
    summary = projection["graph_summary"]
    edge_types = summary["edges_by_type"]

    assert projection["status"] == "ready"
    assert projection["phase_5_ready"] is True
    assert summary["nodes_by_type"]["payment"] == 2
    assert summary["nodes_by_type"]["vendor"] == 2
    assert summary["nodes_by_type"]["employee"] == 1
    assert edge_types["payment_to_vendor"] == 2
    assert edge_types["employee_approved_payment"] == 2
    assert edge_types["payment_to_document"] == 2
    assert edge_types["vendor_uses_bank_account"] == 2
    assert projection["recommended_action"]["type"] == "review_relational_graph_projection"


def test_relational_graph_projection_deduplicates_nodes_and_edges() -> None:
    projection = build_relational_graph_projection(_ready_sources())
    nodes = {node["id"]: node for node in projection["nodes"]}
    edges = {edge["id"]: edge for edge in projection["edges"]}

    assert list(nodes).count("vendor:vendor-1") == 1
    shared_account_edge = edges["vendor_uses_bank_account:vendor:vendor-1->bank_account:bank-1"]
    assert sorted(shared_account_edge["evidence_ids"]) == ["rel-1", "txn-1"]


def test_relational_graph_projection_surfaces_relationship_insights() -> None:
    projection = build_relational_graph_projection(_ready_sources())
    insight_types = {insight["insight_type"]: insight for insight in projection["relationship_insights"]}

    assert "vendors_sharing_bank_account" in insight_types
    assert insight_types["vendors_sharing_bank_account"]["entities"]["bank_account"] == "bank_account:bank-1"
    assert "employee_vendor_relationships" in insight_types
    assert "vendor_related_pairs" in insight_types


def test_relational_graph_projection_answer_summarizes_ready_projection() -> None:
    projection = build_relational_graph_projection(_ready_sources())

    answer = synthesize_relational_graph_projection_answer(projection)

    assert "Read-only relational graph projection:" in answer
    assert "nodes" in answer
    assert "edges" in answer
