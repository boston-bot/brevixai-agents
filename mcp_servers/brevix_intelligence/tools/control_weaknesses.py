from __future__ import annotations

from typing import Any

from app.tools.laravel import LaravelToolClient

from ..client import fetch_transactions
from ..config import get_mcp_settings
from ..schemas.evidence import EvidenceItem
from ..schemas.findings import Finding, ToolResult


def _analyze_control_weaknesses(
    transactions: list[dict[str, Any]],
    min_amount: float,
    approver_dominance_threshold: float,
) -> list[Finding]:
    findings: list[Finding] = []
    above_threshold = [
        txn for txn in transactions if float(txn.get("amount", 0)) >= min_amount
    ]

    if not above_threshold:
        return []

    # --- Missing approval ---
    unapproved = [
        txn for txn in above_threshold
        if not txn.get("approved_by", "")
    ]
    if unapproved:
        pct_unapproved = len(unapproved) / len(above_threshold)
        confidence = round(min(0.92, 0.50 + pct_unapproved * 0.5), 2)
        severity = "high" if pct_unapproved >= 0.30 else "medium" if pct_unapproved >= 0.10 else "low"

        evidence = [
            EvidenceItem(
                transaction_id=str(txn["id"]),
                vendor=txn.get("vendor", "Unknown"),
                amount=float(txn.get("amount", 0)),
                date=txn.get("date", ""),
                description="No approval recorded.",
            )
            for txn in unapproved[:5]
        ]

        findings.append(
            Finding(
                risk_type="missing_approval",
                severity=severity,
                confidence=confidence,
                summary=(
                    f"{len(unapproved)} of {len(above_threshold)} transactions "
                    f"above ${min_amount:,.0f} have no recorded approval "
                    f"({pct_unapproved:.1%})."
                ),
                evidence=evidence,
                recommended_next_steps=[
                    "Implement a mandatory approval workflow for transactions above the threshold.",
                    "Retroactively confirm authorization for flagged transactions.",
                    "Review whether approval records exist outside the system.",
                ],
                metadata={
                    "unapproved_count": len(unapproved),
                    "total_above_threshold": len(above_threshold),
                    "pct_unapproved": round(pct_unapproved, 4),
                    "min_amount_threshold": min_amount,
                },
            )
        )

    # --- Missing documentation ---
    undocumented = [
        txn for txn in above_threshold
        if not txn.get("document_id", "")
    ]
    if undocumented:
        pct_undocumented = len(undocumented) / len(above_threshold)
        confidence = round(min(0.90, 0.45 + pct_undocumented * 0.5), 2)
        severity = "high" if pct_undocumented >= 0.40 else "medium" if pct_undocumented >= 0.15 else "low"

        evidence = [
            EvidenceItem(
                transaction_id=str(txn["id"]),
                vendor=txn.get("vendor", "Unknown"),
                amount=float(txn.get("amount", 0)),
                date=txn.get("date", ""),
                description="No supporting document attached.",
            )
            for txn in undocumented[:5]
        ]

        findings.append(
            Finding(
                risk_type="missing_documentation",
                severity=severity,
                confidence=confidence,
                summary=(
                    f"{len(undocumented)} of {len(above_threshold)} transactions "
                    f"above ${min_amount:,.0f} have no attached document "
                    f"({pct_undocumented:.1%})."
                ),
                evidence=evidence,
                recommended_next_steps=[
                    "Request invoices or receipts for all undocumented transactions.",
                    "Enforce document attachment requirements in the payment workflow.",
                    "Audit the completeness of historical transaction records.",
                ],
                metadata={
                    "undocumented_count": len(undocumented),
                    "total_above_threshold": len(above_threshold),
                    "pct_undocumented": round(pct_undocumented, 4),
                    "min_amount_threshold": min_amount,
                },
            )
        )

    # --- Approval concentration (single approver dominance) ---
    approver_counts: dict[str, int] = {}
    approved_txns = [txn for txn in above_threshold if txn.get("approved_by", "")]
    for txn in approved_txns:
        approver = str(txn["approved_by"])
        approver_counts[approver] = approver_counts.get(approver, 0) + 1

    if approved_txns and approver_counts:
        top_approver, top_count = max(approver_counts.items(), key=lambda x: x[1])
        top_pct = top_count / len(approved_txns)

        if top_pct >= approver_dominance_threshold:
            confidence = round(min(0.88, 0.55 + top_pct * 0.35), 2)

            example_txns = [
                txn for txn in approved_txns
                if str(txn.get("approved_by", "")) == top_approver
            ][:5]

            evidence = [
                EvidenceItem(
                    transaction_id=str(txn["id"]),
                    vendor=txn.get("vendor", "Unknown"),
                    amount=float(txn.get("amount", 0)),
                    date=txn.get("date", ""),
                    description=f"Approved by {top_approver}.",
                )
                for txn in example_txns
            ]

            findings.append(
                Finding(
                    risk_type="approval_concentration",
                    severity="medium",
                    confidence=confidence,
                    summary=(
                        f"A single approver ({top_approver}) authorized {top_pct:.1%} "
                        f"of approved transactions ({top_count} of {len(approved_txns)}). "
                        "This indicates insufficient segregation of duties."
                    ),
                    evidence=evidence,
                    recommended_next_steps=[
                        "Review whether a second approver is required for high-value transactions.",
                        "Assess whether the sole approver has a conflict of interest with any vendors.",
                        "Implement dual-control approval for transactions above a defined threshold.",
                    ],
                    metadata={
                        "top_approver": top_approver,
                        "top_approver_count": top_count,
                        "total_approved": len(approved_txns),
                        "dominance_pct": round(top_pct, 4),
                        "dominance_threshold": approver_dominance_threshold,
                    },
                )
            )

    return findings


async def summarize_control_weaknesses(
    client: LaravelToolClient,
    company_id: str,
    user_id: str = "mcp_service",
) -> ToolResult:
    from datetime import datetime, timezone

    analyzed_at = datetime.now(timezone.utc).isoformat()
    settings = get_mcp_settings()

    transactions = await fetch_transactions(
        client,
        company_id=company_id,
        limit=settings.max_transactions,
        user_id=user_id,
    )

    if not transactions:
        return ToolResult(
            tool_name="summarize_control_weaknesses",
            company_id=company_id,
            analyzed_at=analyzed_at,
            status="no_data",
        )

    findings = _analyze_control_weaknesses(
        transactions,
        min_amount=settings.control_weakness_min_amount,
        approver_dominance_threshold=settings.control_weakness_approver_dominance,
    )

    return ToolResult(
        tool_name="summarize_control_weaknesses",
        company_id=company_id,
        findings=findings,
        analyzed_at=analyzed_at,
        status="ok",
    )
