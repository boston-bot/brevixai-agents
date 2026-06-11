"""CLI utilities for the V1 manual AI-assisted fraud testing workflow.

Usage examples:

    # Generate prompt files for ALL pending scenarios
    python -m app.fraud_testing.cli batch-prompts \
        --api-url http://localhost:8000 --token your-token --output-dir ./fraud_prompts

    # After saving ChatGPT responses as *_extraction.json / *_mock_data.json:

    # Validate all files in the folder at once
    python -m app.fraud_testing.cli batch-validate ./fraud_prompts

    # Import all validated files into Laravel at once
    python -m app.fraud_testing.cli batch-import ./fraud_prompts \
        --api-url http://localhost:8000 --token your-token

    # Single-file helpers
    python -m app.fraud_testing.cli prompt-extraction --narrative "A payroll manager..."
    python -m app.fraud_testing.cli prompt-mock-data extraction.json
    python -m app.fraud_testing.cli validate-extraction extraction.json
    python -m app.fraud_testing.cli validate-mock-data mock_data.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from app.fraud_testing.validators import (
    check_mock_data_minimums,
    load_and_validate_extraction_file,
    load_and_validate_mock_data_file,
)


PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text()


def _fetch_pending_scenarios(api_url: str, token: str, limit: int) -> list[dict]:
    url = f"{api_url.rstrip('/')}/api/internal/fraud-scenarios/pending?limit={limit}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            return body.get("data", [])
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API returned {e.code}: {e.read().decode()}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach API at {api_url}: {e.reason}") from e


# ─── Commands ────────────────────────────────────────────────────────────────


def cmd_prompt_extraction(args: argparse.Namespace) -> int:
    narrative = args.narrative
    if not narrative and args.file:
        narrative = Path(args.file).read_text().strip()
    if not narrative:
        print("ERROR: provide --narrative TEXT or --file PATH", file=sys.stderr)
        return 1

    template = _load_prompt("fraud_extraction_v1.md")
    print(template.replace("{{NARRATIVE}}", narrative))
    return 0


def cmd_batch_prompts(args: argparse.Namespace) -> int:
    api_url = args.api_url or os.environ.get("BREVIX_API_BASE_URL", "http://localhost:8000")
    token = args.token or os.environ.get("BREVIX_INTERNAL_AGENT_TOKEN", "")
    limit = args.limit
    output_dir = Path(args.output_dir)

    if not token:
        print("ERROR: --token is required (or set BREVIX_INTERNAL_AGENT_TOKEN)", file=sys.stderr)
        return 1

    print(f"Fetching up to {limit} pending scenarios from {api_url}...")
    try:
        scenarios = _fetch_pending_scenarios(api_url, token, limit)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if not scenarios:
        print("No pending scenarios found.")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    template = _load_prompt("fraud_extraction_v1.md")

    print(f"Found {len(scenarios)} scenario(s). Writing prompt files to {output_dir}/\n")

    for scenario in scenarios:
        scenario_id = scenario["id"]
        external_id = scenario.get("external_scenario_id") or scenario_id[:8]
        title = scenario.get("title", "Untitled")
        narrative = scenario.get("narrative", "")

        # Write the prompt
        prompt_text = template.replace("{{NARRATIVE}}", narrative)
        prompt_file = output_dir / f"{external_id}_extraction_prompt.txt"
        prompt_file.write_text(prompt_text)

        # Write a small metadata file so it's easy to know which scenario this belongs to
        meta = {"id": scenario_id, "external_scenario_id": external_id, "title": title}
        meta_file = output_dir / f"{external_id}_meta.json"
        meta_file.write_text(json.dumps(meta, indent=2))

        print(f"  [{external_id}] {title}")
        print(f"    prompt  → {prompt_file}")
        print(f"    meta    → {meta_file}")
        print(f"    After ChatGPT, save response as: {output_dir}/{external_id}_extraction.json")
        print()

    print("─" * 60)
    print("Next steps:")
    print("  1. Open each *_extraction_prompt.txt in ChatGPT")
    print("  2. Save the JSON response as *_extraction.json in the same folder")
    print("  3. Validate: python -m app.fraud_testing.cli validate-extraction <file>")
    print("  4. Import:   curl -X POST .../api/internal/fraud-scenarios/{id}/extraction \\")
    print("                    -H 'Authorization: Bearer <token>' \\")
    print("                    -H 'Content-Type: application/json' \\")
    print("                    -d @<file>")
    return 0


def cmd_prompt_mock_data(args: argparse.Namespace) -> int:
    extraction_path = args.extraction
    data, result = load_and_validate_extraction_file(extraction_path)
    if not result:
        print("ERROR: extraction.json is invalid:", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    template = _load_prompt("mock_data_generation_v1.md")
    extraction_json = json.dumps(data, indent=2)
    print(template.replace("{{STRUCTURED_EXTRACTION_JSON}}", extraction_json))
    return 0


def cmd_validate_extraction(args: argparse.Namespace) -> int:
    data, result = load_and_validate_extraction_file(args.file)
    if result:
        print("✓ extraction.json is valid")
        print(f"  fraud_category: {data.get('fraud_category', 'N/A')}")
        print(f"  indicators: {len(data.get('expected_indicators', []))}")
        print(f"  findings: {len(data.get('expected_findings', []))}")
        return 0
    else:
        print("✗ extraction.json is invalid:", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1


def _post_json(url: str, token: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection error: {e.reason}") from e


def cmd_batch_validate(args: argparse.Namespace) -> int:
    folder = Path(args.folder)
    if not folder.exists():
        print(f"ERROR: folder not found: {folder}", file=sys.stderr)
        return 1

    extraction_files = sorted(folder.glob("*_extraction.json"))
    mock_data_files = sorted(folder.glob("*_mock_data.json"))

    if not extraction_files and not mock_data_files:
        print(f"No *_extraction.json or *_mock_data.json files found in {folder}")
        return 0

    all_passed = True

    if extraction_files:
        print(f"── Extraction files ({len(extraction_files)}) ──────────────────")
        for path in extraction_files:
            _, result = load_and_validate_extraction_file(path)
            if result:
                print(f"  ✓  {path.name}")
            else:
                print(f"  ✗  {path.name}")
                for err in result.errors:
                    print(f"       {err}")
                all_passed = False

    if mock_data_files:
        print(f"\n── Mock data files ({len(mock_data_files)}) ──────────────────")
        for path in mock_data_files:
            data, result = load_and_validate_mock_data_file(path)
            if not result:
                print(f"  ✗  {path.name} (schema)")
                for err in result.errors:
                    print(f"       {err}")
                all_passed = False
                continue
            minimums = check_mock_data_minimums(data)
            if not minimums:
                print(f"  ✗  {path.name} (minimums)")
                for err in minimums.errors:
                    print(f"       {err}")
                all_passed = False
            else:
                print(f"  ✓  {path.name}")

    print()
    if all_passed:
        print("All files valid. Ready to import.")
    else:
        print("Fix the errors above before importing.")
    return 0 if all_passed else 1


def cmd_batch_import(args: argparse.Namespace) -> int:
    folder = Path(args.folder)
    api_url = (args.api_url or os.environ.get("BREVIX_API_BASE_URL", "http://localhost:8000")).rstrip("/")
    token = args.token or os.environ.get("BREVIX_INTERNAL_AGENT_TOKEN", "")

    if not token:
        print("ERROR: --token is required (or set BREVIX_INTERNAL_AGENT_TOKEN)", file=sys.stderr)
        return 1
    if not folder.exists():
        print(f"ERROR: folder not found: {folder}", file=sys.stderr)
        return 1

    # Find all meta files — each represents one scenario
    meta_files = sorted(folder.glob("*_meta.json"))
    if not meta_files:
        print(f"No *_meta.json files found in {folder}. Run batch-prompts first.", file=sys.stderr)
        return 1

    success = 0
    skipped = 0
    failed = 0

    for meta_file in meta_files:
        meta = json.loads(meta_file.read_text())
        scenario_id = meta["id"]
        external_id = meta.get("external_scenario_id", scenario_id[:8])
        title = meta.get("title", "")

        print(f"\n[{external_id}] {title}")

        extraction_file = folder / f"{external_id}_extraction.json"
        mock_data_file = folder / f"{external_id}_mock_data.json"

        # Import extraction if present
        if extraction_file.exists():
            data, result = load_and_validate_extraction_file(extraction_file)
            if not result:
                print(f"  ✗ extraction skipped — invalid: {'; '.join(result.errors)}")
                failed += 1
            elif not args.extraction_only is False or not args.mock_data_only:
                try:
                    _post_json(f"{api_url}/api/internal/fraud-scenarios/{scenario_id}/extraction", token, data)
                    print(f"  ✓ extraction imported")
                    success += 1
                except RuntimeError as e:
                    print(f"  ✗ extraction failed — {e}")
                    failed += 1
        else:
            if not args.mock_data_only:
                print(f"  – extraction skipped (no file: {extraction_file.name})")
                skipped += 1

        # Import mock data if present
        if mock_data_file.exists():
            data, result = load_and_validate_mock_data_file(mock_data_file)
            if not result:
                print(f"  ✗ mock data skipped — invalid: {'; '.join(result.errors)}")
                failed += 1
            elif not args.extraction_only:
                try:
                    _post_json(f"{api_url}/api/internal/fraud-scenarios/{scenario_id}/mock-data", token, data)
                    print(f"  ✓ mock data imported")
                    success += 1
                except RuntimeError as e:
                    print(f"  ✗ mock data failed — {e}")
                    failed += 1
        else:
            if not args.extraction_only:
                print(f"  – mock data skipped (no file: {mock_data_file.name})")
                skipped += 1

    print(f"\n── Summary ──────────────────────────────────────")
    print(f"  Imported: {success}  |  Skipped: {skipped}  |  Failed: {failed}")
    return 0 if failed == 0 else 1


def cmd_validate_mock_data(args: argparse.Namespace) -> int:
    data, result = load_and_validate_mock_data_file(args.file)
    if not result:
        print("✗ mock_data.json schema validation failed:", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    minimums = check_mock_data_minimums(data)
    if not minimums:
        print("✗ mock_data.json does not meet minimum requirements:", file=sys.stderr)
        for err in minimums.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    parties = data.get("parties", [])
    transactions = data.get("transactions", [])
    fraudulent = [t for t in transactions if t.get("is_fraudulent")]

    print("✓ mock_data.json is valid")
    print(f"  company: {data.get('mock_company', {}).get('company_name', 'N/A')}")
    print(f"  parties: {len(parties)}")
    print(f"  transactions: {len(transactions)} ({len(fraudulent)} fraudulent)")
    return 0


# ─── Argument parser ─────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.fraud_testing.cli",
        description="Brevix fraud testing CLI utilities",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # prompt-extraction (single)
    p_extraction = subparsers.add_parser(
        "prompt-extraction",
        help="Print the ChatGPT extraction prompt for a single narrative",
    )
    p_extraction.add_argument("--narrative", help="Narrative text inline")
    p_extraction.add_argument("--file", help="Path to a .txt file containing the narrative")

    # batch-prompts (all pending from API)
    p_batch = subparsers.add_parser(
        "batch-prompts",
        help="Fetch all pending scenarios from the API and write a prompt file for each",
    )
    p_batch.add_argument("--api-url", help="Laravel API base URL (default: $BREVIX_API_BASE_URL or http://localhost:8000)")
    p_batch.add_argument("--token", help="Bearer token (default: $BREVIX_INTERNAL_AGENT_TOKEN)")
    p_batch.add_argument("--limit", type=int, default=50, help="Max scenarios to fetch (default: 50)")
    p_batch.add_argument("--output-dir", default="./fraud_prompts", help="Directory to write prompt files (default: ./fraud_prompts)")

    # prompt-mock-data
    p_mock = subparsers.add_parser(
        "prompt-mock-data",
        help="Print the ChatGPT mock data prompt for a validated extraction.json",
    )
    p_mock.add_argument("extraction", help="Path to extraction.json")

    # batch-validate
    p_bv = subparsers.add_parser(
        "batch-validate",
        help="Validate all *_extraction.json and *_mock_data.json files in a folder",
    )
    p_bv.add_argument("folder", help="Folder containing the JSON files (from batch-prompts)")

    # batch-import
    p_bi = subparsers.add_parser(
        "batch-import",
        help="Import all validated JSON files in a folder into Laravel",
    )
    p_bi.add_argument("folder", help="Folder containing the JSON files (from batch-prompts)")
    p_bi.add_argument("--api-url", help="Laravel API base URL (default: $BREVIX_API_BASE_URL or http://localhost:8000)")
    p_bi.add_argument("--token", help="Bearer token (default: $BREVIX_INTERNAL_AGENT_TOKEN)")
    p_bi.add_argument("--extraction-only", action="store_true", help="Only import extraction files, skip mock data")
    p_bi.add_argument("--mock-data-only", action="store_true", help="Only import mock data files, skip extraction")

    # validate-extraction
    p_ve = subparsers.add_parser("validate-extraction", help="Validate a single extraction.json file")
    p_ve.add_argument("file", help="Path to extraction.json")

    # validate-mock-data
    p_vm = subparsers.add_parser("validate-mock-data", help="Validate a single mock_data.json file")
    p_vm.add_argument("file", help="Path to mock_data.json")

    args = parser.parse_args()

    handlers = {
        "prompt-extraction": cmd_prompt_extraction,
        "batch-prompts": cmd_batch_prompts,
        "batch-validate": cmd_batch_validate,
        "batch-import": cmd_batch_import,
        "prompt-mock-data": cmd_prompt_mock_data,
        "validate-extraction": cmd_validate_extraction,
        "validate-mock-data": cmd_validate_mock_data,
    }

    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
