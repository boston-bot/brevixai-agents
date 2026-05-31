"""Smoke test deployed Laravel/RDS IRS knowledge endpoints.

Usage:
    python scripts/smoke_irs_knowledge.py --production
    python scripts/smoke_irs_knowledge.py --base-url https://api.example.com --tool-key ...
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.irs_procedural import IrsToolRequest, synthesize_irs_answer
from app.tools.laravel import LaravelToolClient


SMOKE_CASES = [
    {
        "id": "levy_notice",
        "request": IrsToolRequest("irm_search", "levy notice"),
        "expect_empty": False,
        "expect_prefixes": ["5.11.", "5.19."],
    },
    {
        "id": "cp504",
        "request": IrsToolRequest("irs_notice_type", "CP504"),
        "expect_empty": False,
        "expect_prefixes": ["5.11.", "5.19."],
    },
    {
        "id": "lt11",
        "request": IrsToolRequest("irs_notice_type", "LT11"),
        "expect_empty": False,
        "expect_prefixes": ["5.11.", "5.19."],
    },
    {
        "id": "cp2000",
        "request": IrsToolRequest("irs_notice_type", "CP2000"),
        "expect_empty": False,
        "expect_prefixes": ["4.19.", "20.1.", "4.10."],
    },
    {
        "id": "trust_fund_recovery_penalty",
        "request": IrsToolRequest("irs_collection_risk", "trust fund recovery penalty"),
        "expect_empty": False,
        "expect_prefixes": ["5.7.", "8.25.", "20.1."],
    },
    {
        "id": "unknown_notice_code",
        "request": IrsToolRequest("irs_notice_type", "CP9999"),
        "expect_empty": True,
        "expect_prefixes": [],
    },
]


async def _call_tool(client: LaravelToolClient, request: IrsToolRequest, user_id: str) -> dict[str, Any]:
    if request.tool_name == "irm_search":
        return await client.irm_search(request.query, limit=request.limit, user_id=user_id)
    if request.tool_name == "irm_section":
        return await client.irm_section(request.query, user_id=user_id)
    if request.tool_name == "irs_notice_type":
        return await client.irs_notice_type(request.query, limit=request.limit, user_id=user_id)
    if request.tool_name == "irs_records_checklist":
        return await client.irs_records_checklist(request.query, limit=request.limit, user_id=user_id)
    if request.tool_name == "irs_collection_risk":
        return await client.irs_collection_risk(request.query, limit=request.limit, user_id=user_id)
    raise ValueError(f"Unsupported IRS smoke tool: {request.tool_name}")


def _has_results(payload: dict[str, Any]) -> bool:
    for key in ("results", "sections", "matches", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return bool(value)
    return any(isinstance(payload.get(key), dict) for key in ("result", "section", "data"))


def _top_irm_reference(payload: dict[str, Any]) -> str | None:
    for key in ("results", "sections", "matches", "items"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                return first.get("irm_reference")
    return None


def _checks(case: dict[str, Any], payload: dict[str, Any], answer: str) -> list[str]:
    failures: list[str] = []
    has_results = _has_results(payload)
    if "irm_reference:" not in answer:
        failures.append("answer missing irm_reference")
    if "Disclaimer:" not in answer:
        failures.append("answer missing disclaimer")
    if case["expect_empty"]:
        if has_results:
            failures.append("unknown notice code unexpectedly returned source results")
        if "No source-backed IRM result was returned" not in answer:
            failures.append("empty result did not produce no-source response")
    else:
        if not has_results:
            failures.append("expected source results but received empty payload")
        expected_prefixes: list[str] = case.get("expect_prefixes", [])
        if expected_prefixes and has_results:
            top_ref = _top_irm_reference(payload)
            if top_ref is None:
                failures.append("could not extract top irm_reference from results")
            elif not any(top_ref.startswith(p) for p in expected_prefixes):
                failures.append(
                    f"top result {top_ref!r} does not match expected prefixes {expected_prefixes}"
                )
    return failures


async def run_smokes(base_url: str, tool_key: str, timeout_seconds: float, user_id: str) -> list[dict[str, Any]]:
    client = LaravelToolClient(base_url, tool_key, timeout_seconds=timeout_seconds)
    results: list[dict[str, Any]] = []

    for case in SMOKE_CASES:
        request = case["request"]
        started = time.perf_counter()
        try:
            payload = await _call_tool(client, request, user_id)
            answer = synthesize_irs_answer(request, payload)
            failures = _checks(case, payload, answer)
            results.append(
                {
                    "id": case["id"],
                    "request": asdict(request),
                    "passed": not failures,
                    "failures": failures,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    "payload_status": payload.get("status") if isinstance(payload, dict) else None,
                    "answer_preview": answer[:240],
                }
            )
        except Exception as exc:
            results.append(
                {
                    "id": case["id"],
                    "request": asdict(request),
                    "passed": False,
                    "failures": [f"{exc.__class__.__name__}: {exc}"],
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )

    return results


def _print_report(results: list[dict[str, Any]]) -> None:
    passed = sum(1 for result in results if result["passed"])
    print(f"IRS knowledge smoke: {passed}/{len(results)} passed")
    for result in results:
        label = "PASS" if result["passed"] else "FAIL"
        print(f"[{label}] {result['id']} ({result['latency_ms']}ms)")
        for failure in result.get("failures", []):
            print(f"  - {failure}")


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Smoke test deployed IRS knowledge endpoints.")
    parser.add_argument("--base-url", default=settings.laravel_base_url)
    parser.add_argument("--tool-key", default=settings.laravel_agent_tool_key)
    parser.add_argument("--timeout", type=float, default=settings.http_timeout_seconds)
    parser.add_argument("--user-id", default="irs_smoke")
    parser.add_argument("--production", action="store_true", help="Fail fast if the target is localhost.")
    parser.add_argument("--json-output", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.production and ("localhost" in args.base_url or "127.0.0.1" in args.base_url):
        print("Production smoke requires a deployed BREVIX_LARAVEL_BASE_URL, not localhost.", file=sys.stderr)
        return 2
    if not args.tool_key:
        print("BREVIX_LARAVEL_AGENT_TOOL_KEY is required for IRS smoke tests.", file=sys.stderr)
        return 2

    results = asyncio.run(run_smokes(args.base_url, args.tool_key, args.timeout, args.user_id))
    _print_report(results)

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        with args.json_output.open("w") as f:
            json.dump(results, f, indent=2)
        print(f"Saved JSON results to {args.json_output}")

    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
