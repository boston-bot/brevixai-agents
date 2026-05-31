# Phase 2C IRS IRM Validation

Date: 2026-05-31

## Scope

Phase 2C validates the existing parsed IRM tables and guarded IRS routing before any embeddings or document extraction work.

Validated prompts:

- `levy notice`
- `CP504`
- `LT11`
- `CP2000`
- `trust fund recovery penalty`
- unknown notice code, using `CP9999`

## Changes Completed

### Agent Service

- Added guarded LangGraph routing for IRS procedural questions only.
- Added deterministic IRM answer synthesis with required `irm_reference` and disclaimer text.
- Added IRS answer-quality fixtures for citation, disclaimer, empty-result behavior, and exact section lookup.
- Added a smoke runner at `scripts/smoke_irs_knowledge.py`.

### Laravel API

- Mapped notice codes through deterministic synonyms for records/checklist and collection-risk queries.
- Added exact section lookup fallback for:
  - exact `irm_sections.irm_reference`
  - document-level `irm_documents.irm_reference`
  - descendant section groups when the requested parent reference is not stored as its own row
- Added Laravel regression coverage in `tests/Feature/IrmKnowledgeToolTest.php`.

## Validation Results

### Automated Tests

- `brevixai-api`: `php artisan test tests/Feature/IrmKnowledgeToolTest.php`
  - Result: 12 passed, 43 assertions
- `brevixai-agents`: `.venv/bin/python -m pytest tests/test_irs_answer_quality.py tests/test_router.py mcp_servers/brevix_intelligence/tests/test_irs_knowledge.py tests/test_laravel_tool_client.py`
  - Result: 23 passed

### Local Smoke Script

Command:

```bash
.venv/bin/python scripts/smoke_irs_knowledge.py \
  --base-url http://127.0.0.1:8000 \
  --tool-key local-dev-key \
  --json-output reports/irs_smoke_local.json
```

Result: 6/6 passed.

This confirms the endpoints return safe, cited, disclaimer-bearing responses and do not fabricate guidance for unknown notice codes.

### UI-Path Agent Smoke

The local agent endpoint that Rex calls was tested with the same user-facing prompts. The route returned `irs_procedural_question`, citations, and disclaimers.

Important quality finding: `Look up IRM 5.11.1.1.` still returns no source-backed result because the local parsed IRM corpus does not contain Part 5 collection IRM records.

Current local parsed corpus:

| Document | Title |
|---|---|
| `8.1.6` | Disclosure, Security and Outside Contacts |
| `9.5.1` | Administrative Investigations and General Investigative Procedures |
| `9.5.14` | Closing Procedures |

## Quality Assessment

Phase 2C is functionally wired, but not yet substantively strong enough for broader routing.

Observed issue: keyword/ILIKE search returns cited results, but for IRS collection and notice questions the top results are often from Appeals or Criminal Investigation procedure sections rather than collection-specific Part 5 sections.

This is a data/ranking problem, not an embeddings problem yet.

## Next Phase Recommendation

Do **Phase 2D: IRM corpus coverage and lexical ranking** before embeddings.

Phase 2D should:

1. Verify IRM ingestion includes collection-focused Part 5 documents needed for levy, lien, balance due, and notice workflows.
2. Add a corpus coverage smoke check for expected references or prefixes, especially `5.11.*`, `5.12.*`, `5.14.*`, `5.19.*`, and trust-fund-recovery-related sections.
3. Replace simple OR-based ILIKE ordering with deterministic lexical ranking:
   - exact reference match
   - notice-code synonym match
   - phrase match
   - all-terms match
   - title/document-title boost
   - section prefix boost for known issue families
4. Re-run the six Phase 2C smoke prompts and require useful source relevance, not only citations/disclaimers.

Only consider vector embeddings after Phase 2D proves that a complete enough corpus plus deterministic lexical ranking still misses semantically obvious procedural sections.
