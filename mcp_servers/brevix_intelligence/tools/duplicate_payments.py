from __future__ import annotations

from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Any

from app.tools.laravel import LaravelToolClient

from ..client import fetch_transactions
from ..config import get_mcp_settings
from ..schemas.evidence import EvidenceItem
from ..schemas.findings import Finding, ToolResult


def _normalize_vendor(name: str) -> str:
    return " ".join(name.lower().strip().split())


def _parse_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _amount_match(a: float, b: float, tolerance: float) -> float:
    if a <= 0 or b <= 0:
        return 0.0
    diff_ratio = abs(a - b) / max(a, b)
    if diff_ratio > tolerance * 5:
        return 0.0
    return max(0.0, 1.0 - diff_ratio / tolerance)


def _str_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _severity_from_confidence(confidence: float) -> str:
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.70:
        return "medium"
    if confidence >= 0.50:
        return "low"
    return "info"


def _analyze_duplicates(
    transactions: list[dict[str, Any]],
    amount_tolerance: float,
    date_window_days: int,
) -> list[Finding]:
    findings: list[Finding] = []
    by_vendor: dict[str, list[dict[str, Any]]] = {}

    for txn in transactions:
        amt = float(txn.get("amount", 0))
        if amt <= 0:
            continue
        key = _normalize_vendor(txn.get("vendor", ""))
        by_vendor.setdefault(key, []).append(txn)

    seen_pairs: set[frozenset] = set()

    for txns in by_vendor.values():
        if len(txns) < 2:
            continue

        for i, a in enumerate(txns):
            for b in txns[i + 1 :]:
                pair_key = frozenset([a["id"], b["id"]])
                if pair_key in seen_pairs:
                    continue

                amt_a = float(a.get("amount", 0))
                amt_b = float(b.get("amount", 0))

                amt_score = _amount_match(amt_a, amt_b, amount_tolerance)
                if amt_score == 0.0:
                    continue

                date_a = _parse_date(a.get("date", ""))
                date_b = _parse_date(b.get("date", ""))
                if not date_a or not date_b:
                    continue

                date_diff = abs((date_a - date_b).days)
                if date_diff > date_window_days:
                    continue

                # Build confidence from matching signals
                confidence = 0.25  # base: same vendor, overlapping amount, within window

                if abs(amt_a - amt_b) < 0.01:
                    confidence += 0.30
                elif amt_score > 0.99:
                    confidence += 0.20
                else:
                    confidence += 0.10

                if date_diff <= 3:
                    confidence += 0.20
                elif date_diff <= 7:
                    confidence += 0.15
                elif date_diff <= 14:
                    confidence += 0.10
                else:
                    confidence += 0.05

                inv_sim = _str_similarity(a.get("invoice_number"), b.get("invoice_number"))
                if inv_sim > 0.9:
                    confidence += 0.20
                elif inv_sim > 0.7:
                    confidence += 0.10

                memo_sim = _str_similarity(a.get("memo"), b.get("memo"))
                if memo_sim > 0.8:
                    confidence += 0.10

                confidence = round(min(1.0, confidence), 2)

                if confidence < 0.40:
                    continue

                seen_pairs.add(pair_key)

                vendor_display = a.get("vendor", "Unknown")
                findings.append(
                    Finding(
                        risk_type="duplicate_payment",
                        severity=_severity_from_confidence(confidence),
                        confidence=confidence,
                        summary=(
                            f"Possible duplicate payment to {vendor_display}: "
                            f"${amt_a:,.2f} on {a.get('date')} and "
                            f"${amt_b:,.2f} on {b.get('date')}."
                        ),
                        evidence=[
                            EvidenceItem(
                                transaction_id=str(a["id"]),
                                vendor=a.get("vendor", ""),
                                amount=amt_a,
                                date=a.get("date", ""),
                                invoice_number=a.get("invoice_number"),
                                memo=a.get("memo"),
                            ),
                            EvidenceItem(
                                transaction_id=str(b["id"]),
                                vendor=b.get("vendor", ""),
                                amount=amt_b,
                                date=b.get("date", ""),
                                invoice_number=b.get("invoice_number"),
                                memo=b.get("memo"),
                            ),
                        ],
                        recommended_next_steps=[
                            "Verify invoice documentation for both transactions.",
                            "Check for void or refund activity on either payment.",
                            "Confirm with vendor whether both payments were received and applied.",
                        ],
                    )
                )

    return findings


async def detect_duplicate_payments(
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
            tool_name="detect_duplicate_payments",
            company_id=company_id,
            analyzed_at=analyzed_at,
            status="no_data",
        )

    findings = _analyze_duplicates(
        transactions,
        amount_tolerance=settings.duplicate_amount_tolerance,
        date_window_days=settings.duplicate_date_window_days,
    )

    return ToolResult(
        tool_name="detect_duplicate_payments",
        company_id=company_id,
        findings=findings,
        analyzed_at=analyzed_at,
        status="ok",
    )
