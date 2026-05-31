from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.tools.laravel import LaravelToolClient

from ..client import fetch_transactions
from ..config import get_mcp_settings
from ..schemas.evidence import EvidenceItem
from ..schemas.findings import Finding, ToolResult


def _parse_month(value: str) -> str | None:
    """Return YYYY-MM from a YYYY-MM-DD date string."""
    try:
        return value[:7]
    except (TypeError, IndexError):
        return None


def _analyze_cash_burn(transactions: list[dict[str, Any]]) -> list[Finding]:
    monthly: dict[str, float] = {}
    monthly_ids: dict[str, list[str]] = {}

    for txn in transactions:
        amt = float(txn.get("amount", 0))
        if amt <= 0:
            continue
        month = _parse_month(txn.get("date", ""))
        if not month:
            continue
        monthly[month] = monthly.get(month, 0.0) + amt
        monthly_ids.setdefault(month, []).append(str(txn["id"]))

    if len(monthly) < 3:
        return []

    months = sorted(monthly.keys())
    values = [monthly[m] for m in months]

    findings: list[Finding] = []

    # Detect month-over-month acceleration over the most recent 3 months
    recent_months = months[-3:]
    recent_values = [monthly[m] for m in recent_months]

    mom_changes = [
        (recent_values[i + 1] - recent_values[i]) / recent_values[i]
        for i in range(len(recent_values) - 1)
        if recent_values[i] > 0
    ]

    if not mom_changes:
        return []

    avg_mom_change = sum(mom_changes) / len(mom_changes)
    all_increasing = all(c > 0 for c in mom_changes)

    # Consecutive months of increase across the full dataset
    consecutive_increases = 0
    for i in range(len(values) - 1, 0, -1):
        if values[i] > values[i - 1]:
            consecutive_increases += 1
        else:
            break

    if avg_mom_change < 0.10 and consecutive_increases < 2:
        return []

    if avg_mom_change >= 0.30 or consecutive_increases >= 4:
        severity = "high"
        confidence = round(min(0.92, 0.65 + avg_mom_change * 0.5), 2)
    elif avg_mom_change >= 0.15 or consecutive_increases >= 3:
        severity = "medium"
        confidence = round(min(0.75, 0.50 + avg_mom_change * 0.5), 2)
    else:
        severity = "low"
        confidence = round(min(0.60, 0.40 + avg_mom_change * 0.5), 2)

    latest_month = recent_months[-1]
    latest_ids = monthly_ids.get(latest_month, [])

    evidence = [
        EvidenceItem(
            transaction_id=txn_id,
            vendor="(monthly aggregate)",
            amount=monthly[latest_month],
            date=latest_month + "-01",
            description=f"Total outflow for {latest_month}: ${monthly[latest_month]:,.2f}",
        )
        for txn_id in latest_ids[:3]
    ]

    monthly_summary = {m: round(monthly[m], 2) for m in recent_months}

    findings.append(
        Finding(
            risk_type="cash_burn_acceleration",
            severity=severity,
            confidence=confidence,
            summary=(
                f"Cash outflow has increased an average of {avg_mom_change:.1%} per month "
                f"over the last {len(recent_months)} months "
                f"({', '.join(f'{m}: ${monthly[m]:,.0f}' for m in recent_months)})."
            ),
            evidence=evidence,
            recommended_next_steps=[
                "Review the largest expense categories driving the increase.",
                "Compare outflow trend against revenue growth to assess sustainability.",
                "Evaluate upcoming commitments and whether current runway is sufficient.",
            ],
            metadata={
                "avg_mom_change_pct": round(avg_mom_change, 4),
                "consecutive_increases": consecutive_increases,
                "monthly_summary": monthly_summary,
            },
        )
    )

    return findings


async def calculate_cash_burn(
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
            tool_name="calculate_cash_burn",
            company_id=company_id,
            analyzed_at=analyzed_at,
            status="no_data",
        )

    findings = _analyze_cash_burn(transactions)

    return ToolResult(
        tool_name="calculate_cash_burn",
        company_id=company_id,
        findings=findings,
        analyzed_at=analyzed_at,
        status="ok",
    )
