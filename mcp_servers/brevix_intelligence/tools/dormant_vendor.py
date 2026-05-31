from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.tools.laravel import LaravelToolClient

from ..client import fetch_transactions
from ..config import get_mcp_settings
from ..schemas.evidence import EvidenceItem
from ..schemas.findings import Finding, ToolResult


def _parse_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _confidence_from_gap(gap_days: int) -> float:
    if gap_days >= 365:
        return 0.90
    if gap_days >= 180:
        return 0.75
    if gap_days >= 120:
        return 0.60
    return 0.50


def _analyze_dormant_reactivation(
    transactions: list[dict[str, Any]],
    dormant_days: int,
    reference_date: date | None = None,
) -> list[Finding]:
    today = reference_date or date.today()
    recent_cutoff = today  # "recent" = any transaction that follows a gap

    # Group by vendor, sorted by date
    by_vendor: dict[str, list[tuple[date, dict[str, Any]]]] = {}
    for txn in transactions:
        amt = float(txn.get("amount", 0))
        if amt <= 0:
            continue
        txn_date = _parse_date(txn.get("date", ""))
        if not txn_date:
            continue
        vendor = txn.get("vendor", "Unknown")
        by_vendor.setdefault(vendor, []).append((txn_date, txn))

    findings: list[Finding] = []

    for vendor, dated_txns in by_vendor.items():
        dated_txns.sort(key=lambda x: x[0])
        dates = [d for d, _ in dated_txns]

        # Find gaps between consecutive transactions
        for i in range(len(dates) - 1):
            gap = (dates[i + 1] - dates[i]).days
            if gap < dormant_days:
                continue

            # There's a gap — check that the reactivation is recent (within the data)
            reactivation_txn = dated_txns[i + 1][1]
            last_before_gap_txn = dated_txns[i][1]

            confidence = _confidence_from_gap(gap)

            findings.append(
                Finding(
                    risk_type="dormant_vendor_reactivation",
                    severity="medium" if confidence >= 0.70 else "low",
                    confidence=round(confidence, 2),
                    summary=(
                        f"{vendor} was inactive for {gap} days "
                        f"(last seen {dates[i]}, reactivated {dates[i + 1]})."
                    ),
                    evidence=[
                        EvidenceItem(
                            transaction_id=str(last_before_gap_txn["id"]),
                            vendor=vendor,
                            amount=float(last_before_gap_txn.get("amount", 0)),
                            date=last_before_gap_txn.get("date", ""),
                            description="Last transaction before dormancy period.",
                        ),
                        EvidenceItem(
                            transaction_id=str(reactivation_txn["id"]),
                            vendor=vendor,
                            amount=float(reactivation_txn.get("amount", 0)),
                            date=reactivation_txn.get("date", ""),
                            description=f"First transaction after {gap}-day gap.",
                        ),
                    ],
                    recommended_next_steps=[
                        "Verify that vendor reactivation was authorized by management.",
                        "Confirm vendor contact information and banking details are still valid.",
                        "Review all recent transactions with this vendor for anomalies.",
                    ],
                    metadata={"gap_days": gap, "dormant_threshold_days": dormant_days},
                )
            )

    return findings


async def detect_dormant_vendor_reactivation(
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
            tool_name="detect_dormant_vendor_reactivation",
            company_id=company_id,
            analyzed_at=analyzed_at,
            status="no_data",
        )

    findings = _analyze_dormant_reactivation(transactions, dormant_days=settings.dormant_vendor_days)

    return ToolResult(
        tool_name="detect_dormant_vendor_reactivation",
        company_id=company_id,
        findings=findings,
        analyzed_at=analyzed_at,
        status="ok",
    )
