from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app.relational_readiness import build_relational_readiness_audit


CORE_EDGE_TYPES = [
    "payment_to_vendor",
    "employee_approved_payment",
    "payment_to_document",
    "vendor_uses_bank_account",
    "employee_shares_address_with_vendor",
    "vendor_related_to_vendor",
]


def build_relational_graph_projection(
    data_sources: dict[str, Any] | None = None,
    *,
    readiness_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a read-only graph-shaped projection from graph-ready payloads."""

    sources = data_sources if isinstance(data_sources, dict) else {}
    audit = readiness_audit if isinstance(readiness_audit, dict) else build_relational_readiness_audit(sources)
    if not audit.get("phase_5_ready"):
        return _blocked_projection(audit)

    builder = _ProjectionBuilder()
    transactions = _transactions_from_sources(sources)
    vendor_payloads = _vendor_payloads(sources.get("vendor_risk"))
    entity_evidence = _entity_evidence(sources.get("entity_relationship_risk"))
    company_context = sources.get("company_context") if isinstance(sources.get("company_context"), dict) else {}

    _add_company_context(builder, company_context)
    for transaction in transactions:
        _add_transaction(builder, transaction, company_context)
    for vendor in vendor_payloads:
        _add_vendor_payload(builder, vendor)
    for evidence in entity_evidence:
        _add_entity_evidence(builder, evidence)

    nodes = builder.nodes()
    edges = builder.edges()
    summary = _graph_summary(nodes, edges)
    insights = _relationship_insights(edges)

    return {
        "projection_type": "relational_graph_projection",
        "status": "ready",
        "phase_5_ready": True,
        "readiness_score": audit.get("readiness_score"),
        "nodes": nodes,
        "edges": edges,
        "graph_summary": {
            **summary,
            "relationship_insight_count": len(insights),
        },
        "relationship_insights": insights,
        "recommended_action": {
            "type": "review_relational_graph_projection",
            "label": "Review relational graph projection",
            "requires_approval": False,
            "payload": {
                "projection_type": "relational_graph_projection",
                "node_count": summary["node_count"],
                "edge_count": summary["edge_count"],
                "relationship_insight_count": len(insights),
            },
        },
        "scope_limitations": [
            "Projection is constructed from agent-visible payloads only.",
            "No graph database, graph infrastructure, alerts, cases, records, or data changes were created.",
        ],
    }


def synthesize_relational_graph_projection_answer(projection: dict[str, Any]) -> str:
    if not isinstance(projection, dict) or projection.get("status") != "ready":
        return ""

    summary = projection.get("graph_summary") if isinstance(projection.get("graph_summary"), dict) else {}
    nodes = summary.get("node_count", 0)
    edges = summary.get("edge_count", 0)
    insights = summary.get("relationship_insight_count", 0)
    return (
        "Read-only relational graph projection: "
        f"{nodes} nodes, {edges} edges, and {insights} relationship insight(s) were built from graph-ready payloads."
    )


class _ProjectionBuilder:
    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: dict[str, dict[str, Any]] = {}

    def add_node(
        self,
        entity_type: str,
        source_id: Any,
        *,
        label: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> str | None:
        normalized_id = _clean_id(source_id)
        if not normalized_id:
            return None
        node_id = f"{entity_type}:{normalized_id}"
        current = self._nodes.get(node_id)
        if current is None:
            self._nodes[node_id] = {
                "id": node_id,
                "entity_type": entity_type,
                "source_id": normalized_id,
                "label": label or normalized_id,
                "properties": _clean_properties(properties or {}),
            }
        else:
            current["properties"] = _merge_properties(current["properties"], properties or {})
            if label and current["label"] == current["source_id"]:
                current["label"] = label
        return node_id

    def add_edge(
        self,
        relationship_type: str,
        source_node_id: str | None,
        target_node_id: str | None,
        *,
        evidence_id: Any = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        if not source_node_id or not target_node_id:
            return
        edge_id = f"{relationship_type}:{source_node_id}->{target_node_id}"
        current = self._edges.get(edge_id)
        evidence_ids = [_clean_id(evidence_id)] if _clean_id(evidence_id) else []
        if current is None:
            self._edges[edge_id] = {
                "id": edge_id,
                "relationship_type": relationship_type,
                "source": source_node_id,
                "target": target_node_id,
                "source_entity_type": source_node_id.split(":", 1)[0],
                "target_entity_type": target_node_id.split(":", 1)[0],
                "evidence_ids": evidence_ids,
                "properties": _clean_properties(properties or {}),
            }
            return

        current["evidence_ids"] = _unique([*current.get("evidence_ids", []), *evidence_ids])
        current["properties"] = _merge_properties(current["properties"], properties or {})

    def nodes(self) -> list[dict[str, Any]]:
        return [self._nodes[node_id] for node_id in sorted(self._nodes)]

    def edges(self) -> list[dict[str, Any]]:
        return [self._edges[edge_id] for edge_id in sorted(self._edges)]


def _blocked_projection(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "projection_type": "relational_graph_projection",
        "status": "blocked",
        "phase_5_ready": False,
        "readiness_score": audit.get("readiness_score"),
        "critical_blockers": audit.get("critical_blockers", []),
        "nodes": [],
        "edges": [],
        "graph_summary": {
            "node_count": 0,
            "edge_count": 0,
            "nodes_by_type": {},
            "edges_by_type": {},
            "high_degree_nodes": [],
            "relationship_insight_count": 0,
        },
        "relationship_insights": [],
        "recommended_action": audit.get("recommended_action"),
        "scope_limitations": [
            "Projection is blocked until the Phase 5 readiness audit passes.",
            "No graph database, graph infrastructure, alerts, cases, records, or data changes were created.",
        ],
    }


def _add_company_context(builder: _ProjectionBuilder, company_context: dict[str, Any]) -> None:
    company_id = company_context.get("company_id")
    user_id = company_context.get("company_user_id") or company_context.get("user_id")
    company_node = builder.add_node(
        "company",
        company_id,
        label=company_context.get("company_name") or company_id,
        properties={"industry": company_context.get("industry")},
    )
    user_node = builder.add_node(
        "company_user",
        user_id,
        properties={"role": company_context.get("user_role")},
    )
    builder.add_edge("company_user_belongs_to_company", user_node, company_node, evidence_id=user_id)


def _add_transaction(builder: _ProjectionBuilder, transaction: dict[str, Any], company_context: dict[str, Any]) -> None:
    payment_id = transaction.get("id") or transaction.get("transaction_id")
    payment_node = builder.add_node(
        "payment",
        payment_id,
        label=f"Payment {payment_id}" if payment_id else None,
        properties={
            "amount": transaction.get("amount"),
            "date": transaction.get("date"),
            "status": transaction.get("status"),
        },
    )
    company_node = builder.add_node("company", transaction.get("company_id") or company_context.get("company_id"))
    user_node = builder.add_node("company_user", transaction.get("company_user_id") or transaction.get("user_id"))
    vendor_node = builder.add_node(
        "vendor",
        transaction.get("vendor_id"),
        label=transaction.get("vendor") or transaction.get("vendor_name"),
    )
    account_node = builder.add_node("bank_account", transaction.get("bank_account_id") or transaction.get("account_id"))
    approver_node = builder.add_node("employee", transaction.get("approved_by") or transaction.get("approver_id"))
    document_node = builder.add_node("document", transaction.get("document_id") or transaction.get("source_document_id"))

    builder.add_edge("payment_scoped_to_company", payment_node, company_node, evidence_id=payment_id)
    builder.add_edge("company_user_initiated_payment", user_node, payment_node, evidence_id=payment_id)
    builder.add_edge("payment_to_vendor", payment_node, vendor_node, evidence_id=payment_id)
    builder.add_edge("employee_approved_payment", approver_node, payment_node, evidence_id=payment_id)
    builder.add_edge("payment_to_document", payment_node, document_node, evidence_id=payment_id)
    builder.add_edge("vendor_uses_bank_account", vendor_node, account_node, evidence_id=payment_id)


def _add_vendor_payload(builder: _ProjectionBuilder, vendor: dict[str, Any]) -> None:
    builder.add_node(
        "vendor",
        vendor.get("vendor_id") or vendor.get("id"),
        label=vendor.get("vendor_name") or vendor.get("name"),
        properties={
            "vendor_risk_score": vendor.get("vendor_risk_score") or vendor.get("risk_score"),
            "risk_level": vendor.get("risk_level"),
        },
    )


def _add_entity_evidence(builder: _ProjectionBuilder, evidence: dict[str, Any]) -> None:
    evidence_id = evidence.get("id") or evidence.get("relationship_id") or evidence.get("entity_id")
    employee_node = builder.add_node(
        "employee",
        evidence.get("employee_id"),
        label=evidence.get("employee_name"),
    )
    vendor_node = builder.add_node(
        "vendor",
        evidence.get("vendor_id"),
        label=evidence.get("vendor_name"),
    )
    account_node = builder.add_node("bank_account", evidence.get("bank_account_id") or evidence.get("account_id"))
    related_vendor_node = builder.add_node(
        "vendor",
        evidence.get("related_vendor_id") or evidence.get("counterparty_vendor_id"),
        label=evidence.get("related_vendor_name") or evidence.get("counterparty_vendor_name"),
    )

    relationship_type = evidence.get("relationship_type")
    builder.add_edge(
        "employee_shares_address_with_vendor",
        employee_node,
        vendor_node,
        evidence_id=evidence_id,
        properties={"relationship_type": relationship_type},
    )
    builder.add_edge(
        "vendor_uses_bank_account",
        vendor_node,
        account_node,
        evidence_id=evidence_id,
        properties={"relationship_type": relationship_type},
    )
    builder.add_edge(
        "vendor_related_to_vendor",
        vendor_node,
        related_vendor_node,
        evidence_id=evidence_id,
        properties={"relationship_type": relationship_type},
    )


def _graph_summary(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    nodes_by_type = Counter(str(node.get("entity_type")) for node in nodes)
    edges_by_type = Counter(str(edge.get("relationship_type")) for edge in edges)
    degree: Counter[str] = Counter()
    node_lookup = {node["id"]: node for node in nodes}
    for edge in edges:
        degree[str(edge.get("source"))] += 1
        degree[str(edge.get("target"))] += 1

    high_degree_nodes = [
        {
            "id": node_id,
            "entity_type": node_lookup.get(node_id, {}).get("entity_type"),
            "label": node_lookup.get(node_id, {}).get("label"),
            "degree": count,
        }
        for node_id, count in degree.most_common(5)
        if node_id in node_lookup and count >= 2
    ]

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes_by_type": dict(sorted(nodes_by_type.items())),
        "edges_by_type": dict(sorted(edges_by_type.items())),
        "high_degree_nodes": high_degree_nodes,
    }


def _relationship_insights(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    account_to_vendors: dict[str, list[dict[str, Any]]] = defaultdict(list)
    employee_vendor_edges: list[dict[str, Any]] = []
    vendor_related_edges: list[dict[str, Any]] = []

    for edge in edges:
        relationship_type = edge.get("relationship_type")
        if relationship_type == "vendor_uses_bank_account":
            account_to_vendors[str(edge.get("target"))].append(edge)
        elif relationship_type == "employee_shares_address_with_vendor":
            employee_vendor_edges.append(edge)
        elif relationship_type == "vendor_related_to_vendor":
            vendor_related_edges.append(edge)

    for account_node, account_edges in sorted(account_to_vendors.items()):
        vendor_nodes = _unique([edge["source"] for edge in account_edges])
        if len(vendor_nodes) < 2:
            continue
        insights.append(
            {
                "insight_type": "vendors_sharing_bank_account",
                "severity": "medium",
                "summary": f"{len(vendor_nodes)} vendors share bank account {account_node}.",
                "entities": {"bank_account": account_node, "vendors": vendor_nodes},
                "evidence_edge_ids": [edge["id"] for edge in account_edges],
            }
        )

    if employee_vendor_edges:
        insights.append(
            {
                "insight_type": "employee_vendor_relationships",
                "severity": "medium",
                "summary": f"{len(employee_vendor_edges)} employee-to-vendor relationship edge(s) are available for review.",
                "entities": {
                    "relationships": [
                        {"employee": edge["source"], "vendor": edge["target"]}
                        for edge in employee_vendor_edges
                    ]
                },
                "evidence_edge_ids": [edge["id"] for edge in employee_vendor_edges],
            }
        )

    if vendor_related_edges:
        insights.append(
            {
                "insight_type": "vendor_related_pairs",
                "severity": "low",
                "summary": f"{len(vendor_related_edges)} vendor-to-vendor relationship edge(s) are available for review.",
                "entities": {
                    "relationships": [
                        {"vendor": edge["source"], "related_vendor": edge["target"]}
                        for edge in vendor_related_edges
                    ]
                },
                "evidence_edge_ids": [edge["id"] for edge in vendor_related_edges],
            }
        )

    return insights


def _transactions_from_sources(sources: dict[str, Any]) -> list[dict[str, Any]]:
    direct = sources.get("transactions")
    if isinstance(direct, list):
        return [item for item in direct if isinstance(item, dict)]

    lookup = sources.get("transaction_lookup")
    if isinstance(lookup, dict) and isinstance(lookup.get("transactions"), list):
        return [item for item in lookup["transactions"] if isinstance(item, dict)]

    context = sources.get("company_context")
    if isinstance(context, dict):
        summary = context.get("transaction_summary")
        if isinstance(summary, dict) and isinstance(summary.get("transactions"), list):
            return [item for item in summary["transactions"] if isinstance(item, dict)]
    return []


def _vendor_payloads(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    vendors = payload.get("vendors")
    if isinstance(vendors, list):
        return [item for item in vendors if isinstance(item, dict)]
    if payload.get("vendor_id") or payload.get("vendor_name") or payload.get("vendor_risk_score") is not None:
        return [payload]
    return []


def _entity_evidence(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    evidence: list[dict[str, Any]] = []
    for key in ("supporting_evidence", "related_entities", "relationships", "entities"):
        value = payload.get(key)
        if isinstance(value, list):
            evidence.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            evidence.append(value)
    return evidence


def _clean_id(value: Any) -> str:
    if value in {None, ""}:
        return ""
    return str(value).strip()


def _clean_properties(properties: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in properties.items() if value is not None and value != ""}


def _merge_properties(current: dict[str, Any], new_values: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    for key, value in _clean_properties(new_values).items():
        if key not in merged:
            merged[key] = value
    return merged


def _unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(text)
    return unique
