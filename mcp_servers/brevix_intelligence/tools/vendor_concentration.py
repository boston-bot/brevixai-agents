from __future__ import annotations

from typing import Any

from app.tools.laravel import LaravelToolClient

from ..client import fetch_transactions
from ..config import get_mcp_settings
from ..schemas.evidence import EvidenceItem
from ..schemas.findings import Finding, ToolResult


def _severity_from_pct(pct: float) -> str:
    if pct >= 0.70:
        return "critical"
    if pct >= 0.50:
        return "high"
    if pct >= 0.40:
        return "medium"
    return "low"


def _analyze_concentration(
    transactions: list[dict[str, Any]],
    threshold: float,
) -> list[Finding]:
    vendor_totals: dict[str, float] = {}
    vendor_txn_ids: dict[str, list[str]] = {}
    vendor_latest_date: dict[str, str] = {}

    for txn in transactions:
        amt = float(txn.get("amount", 0))
        if amt <= 0:
            continue
        vendor = txn.get("vendor", "Unknown")
        vendor_totals[vendor] = vendor_totals.get(vendor, 0.0) + amt
        vendor_txn_ids.setdefault(vendor, []).append(str(txn["id"]))
        current_date = txn.get("date", "")
        if current_date > vendor_latest_date.get(vendor, ""):
            vendor_latest_date[vendor] = current_date

    total_spend = sum(vendor_totals.values())
    if total_spend <= 0:
        return []

    findings: list[Finding] = []

    for vendor, vendor_total in sorted(vendor_totals.items(), key=lambda x: x[1], reverse=True):
        pct = vendor_total / total_spend
        if pct <= threshold:
            continue

        # confidence scales from 0.5 at threshold to 0.95 at 80%+
        confidence = round(min(0.95, 0.5 + (pct - threshold) / (0.80 - threshold) * 0.45), 2)

        txn_ids = vendor_txn_ids[vendor]
        evidence = [
            EvidenceItem(
                transaction_id=txn_id,
                vendor=vendor,
                amount=vendor_total,
                date=vendor_latest_date.get(vendor, ""),
                description=f"{pct:.1%} of total spend (${vendor_total:,.2f} of ${total_spend:,.2f})",
            )
            for txn_id in txn_ids[:5]  # cap evidence items
        ]

        findings.append(
            Finding(
                risk_type="vendor_concentration",
                severity=_severity_from_pct(pct),
                confidence=confidence,
                summary=(
                    f"{vendor} accounts for {pct:.1%} of total spend "
                    f"(${vendor_total:,.2f} of ${total_spend:,.2f} total)."
                ),
                evidence=evidence,
                recommended_next_steps=[
                    "Review contract terms and pricing with this vendor.",
                    "Assess whether concentration creates operational or financial dependency.",
                    "Evaluate whether competitive bidding or alternative vendors should be sourced.",
                ],
                metadata={
                    "vendor": vendor,
                    "vendor_total": round(vendor_total, 2),
                    "total_spend": round(total_spend, 2),
                    "concentration_pct": round(pct, 4),
                    "threshold_pct": threshold,
                },
            )
        )

    return findings


async def analyze_vendor_concentration(
    client: LaravelToolClient,
    company_id: str,
    start_date: str,
    end_date: str,
    user_id: str = "mcp_service",
) -> ToolResult:
    from datetime import datetime, timezone

    analyzed_at = datetime.now(timezone.utc).isoformat()
    settings = get_mcp_settings()

    transactions = await fetch_transactions(
        client,
        company_id=company_id,
        date_from=start_date,
        date_to=end_date,
        limit=settings.max_transactions,
        user_id=user_id,
    )

    if not transactions:
        return ToolResult(
            tool_name="analyze_vendor_concentration",
            company_id=company_id,
            analyzed_at=analyzed_at,
            status="no_data",
        )

    findings = _analyze_concentration(transactions, threshold=settings.vendor_concentration_threshold)

    return ToolResult(
        tool_name="analyze_vendor_concentration",
        company_id=company_id,
        findings=findings,
        analyzed_at=analyzed_at,
        status="ok",
    )
