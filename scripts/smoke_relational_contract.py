"""Smoke test Laravel payloads against the Phase 5B relational contract.

Usage:
    python scripts/smoke_relational_contract.py --company-id company-1 --user-id user-1
    python scripts/smoke_relational_contract.py --production --company-id ... --user-id ...
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.relational_contract_adoption import build_relational_contract_adoption_report
from app.relational_readiness import build_relational_readiness_audit, synthesize_relational_readiness_answer
from app.tools.laravel import LaravelToolClient


async def run_contract_gate(
    client: Any,
    company_id: str,
    user_id: str,
    *,
    transaction_limit: int = 100,
) -> dict[str, Any]:
    started = time.perf_counter()
    data_sources: dict[str, Any] = {}
    tool_failures: list[dict[str, str]] = []

    try:
        data_sources["company_context"] = await client.company_context(company_id, user_id)
    except Exception as exc:
        tool_failures.append(_tool_failure("company_context", exc))

    try:
        data_sources["transaction_lookup"] = await client.transaction_lookup(
            company_id,
            user_id,
            limit=transaction_limit,
        )
    except Exception as exc:
        tool_failures.append(_tool_failure("transaction_lookup", exc))

    try:
        data_sources["vendor_risk"] = await client.vendor_risk(company_id, user_id)
    except Exception as exc:
        tool_failures.append(_tool_failure("vendor_risk", exc))

    try:
        data_sources["entity_relationship_risk"] = await client.entity_relationship_risk(company_id, user_id)
    except Exception as exc:
        tool_failures.append(_tool_failure("entity_relationship_risk", exc))

    audit = build_relational_readiness_audit(data_sources)
    adoption_report = build_relational_contract_adoption_report(audit, tool_failures=tool_failures)
    passed = bool(audit.get("phase_5_ready")) and not tool_failures
    return {
        "passed": passed,
        "company_id": company_id,
        "user_id": user_id,
        "transaction_limit": transaction_limit,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "tool_failures": tool_failures,
        "audit": audit,
        "adoption_report": adoption_report,
        "answer": synthesize_relational_readiness_answer(audit),
    }


def _tool_failure(tool_name: str, exc: Exception) -> dict[str, str]:
    return {
        "tool": tool_name,
        "error_class": exc.__class__.__name__,
        "message": str(exc),
    }


def _print_report(result: dict[str, Any]) -> None:
    audit = result.get("audit") if isinstance(result.get("audit"), dict) else {}
    summary = audit.get("readiness_summary") if isinstance(audit.get("readiness_summary"), dict) else {}
    label = "PASS" if result.get("passed") else "FAIL"

    print(f"Relational contract smoke: {label}")
    print(f"Phase 5 ready: {audit.get('phase_5_ready')} status={audit.get('status')} score={audit.get('readiness_score')}")
    print(
        "Entity contracts ready: "
        f"{summary.get('entity_ready_count', 0)}/{summary.get('entity_contract_count', 0)}; "
        "relationship contracts ready: "
        f"{summary.get('relationship_ready_count', 0)}/{summary.get('relationship_contract_count', 0)}"
    )

    for failure in result.get("tool_failures", []):
        print(f"[TOOL FAIL] {failure['tool']}: {failure['error_class']} {failure['message']}")

    for blocker in audit.get("critical_blockers", [])[:8]:
        missing = ", ".join(str(field) for field in blocker.get("missing_required_fields", []))
        missing_text = f" missing: {missing}" if missing else ""
        print(f"[BLOCKED] {blocker.get('contract')} ({blocker.get('status')}){missing_text}")

    adoption = result.get("adoption_report") if isinstance(result.get("adoption_report"), dict) else {}
    if adoption:
        adoption_label = "READY" if adoption.get("status") == "ready" else "BLOCKED"
        print(f"Laravel payload adoption: {adoption_label}")
        for task in adoption.get("api_remediation_tasks", [])[:6]:
            fields = ", ".join(str(field) for field in task.get("missing_fields", []))
            fields_text = f" missing: {fields}" if fields else ""
            print(f"[API TASK] {task.get('endpoint')} ({task.get('priority')}){fields_text}")

    print(result.get("answer", ""))


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Smoke test Laravel payloads against the Phase 5B relational contract.")
    parser.add_argument("--base-url", default=settings.laravel_base_url)
    parser.add_argument("--tool-key", default=settings.laravel_agent_tool_key)
    parser.add_argument("--timeout", type=float, default=settings.http_timeout_seconds)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--transaction-limit", type=int, default=100)
    parser.add_argument("--production", action="store_true", help="Fail fast if the target is localhost.")
    parser.add_argument("--allow-blocked", action="store_true", help="Return 0 even when Phase 5 is not ready.")
    parser.add_argument("--json-output", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.production and ("localhost" in args.base_url or "127.0.0.1" in args.base_url):
        print("Production smoke requires a deployed BREVIX_LARAVEL_BASE_URL, not localhost.", file=sys.stderr)
        return 2
    if not args.tool_key:
        print("BREVIX_LARAVEL_AGENT_TOOL_KEY is required for relational contract smoke tests.", file=sys.stderr)
        return 2

    client = LaravelToolClient(args.base_url, args.tool_key, timeout_seconds=args.timeout)
    result = asyncio.run(
        run_contract_gate(
            client,
            company_id=args.company_id,
            user_id=args.user_id,
            transaction_limit=args.transaction_limit,
        )
    )
    _print_report(result)

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        with args.json_output.open("w") as f:
            json.dump(result, f, indent=2)
        print(f"Saved JSON results to {args.json_output}")

    return 0 if result["passed"] or args.allow_blocked else 1


if __name__ == "__main__":
    sys.exit(main())
