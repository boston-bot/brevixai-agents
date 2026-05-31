# Phase 2D IRM Quality Progress

Date: 2026-05-31

## Current Position

Phase 2C proved that the IRS/IRM tool path is functionally wired:

- Laravel exposes parsed IRM data through internal agent-tool endpoints.
- The Python MCP adapter calls Laravel instead of querying RDS directly.
- LangGraph has guarded routing for IRS procedural questions only.
- The answer synthesis layer requires source-backed `irm_reference` citations and a professional-services disclaimer.
- Empty IRS results produce a no-source response instead of fabricated procedural guidance.

The local database is now seeded with the full `irm_documents` and `irm_sections` corpus. That changes the immediate priority: Phase 2D should validate and improve keyword search quality over the complete parsed IRM corpus before any vector embedding work starts.

## Completed Work

### Agent/MCP Layer

- `mcp_servers/brevix_intelligence/tools/irs_knowledge.py` is no longer a stub.
- IRS procedural routing is limited to:
  - notice explanations
  - levy, lien, and collection-process questions
  - records-to-gather requests
- The agent avoids tax/legal advice positioning and frames responses as procedural IRM lookups.
- IRS answer-quality fixtures cover:
  - required `irm_reference`
  - required disclaimer
  - no fabricated guidance when source results are empty
  - exact section lookup behavior

### Laravel API Layer

- Notice-code mapping has been added for collection and records-checklist style queries.
- CP504, LT11, and related levy/CDP notice requests now map to levy and collection-process search terms instead of relying only on the raw notice code.
- Exact IRM lookup behavior has been improved to handle stored reference shapes:
  - exact `irm_sections.irm_reference`
  - document-level `irm_documents.irm_reference`
  - descendant section groups when the requested parent reference is not stored as a standalone section row

### Validation Already Run

Recent focused validation passed before the full local corpus was reseeded:

- `brevixai-api`: `php artisan test tests/Feature/IrmKnowledgeToolTest.php`
  - Result: 12 passed
- `brevixai-agents`: IRS quality/router/client tests
  - Result: 23 passed
- Local Laravel smoke via `scripts/smoke_irs_knowledge.py`
  - Result: 6/6 passed for safety checks

Those smoke checks verified source presence, disclaimers, and safe empty-result behavior. They did not yet prove that the top returned sources are the most relevant procedural IRM sections.

## Key Finding

The next risk is search quality, not infrastructure.

With a complete local corpus, simple keyword/ILIKE search can still rank irrelevant low-numbered IRM sections above the procedural sections users expect. For example, collection and notice queries should strongly prefer references like:

- levy and levy notices: `5.11.*`, with supporting collection references such as `5.19.*`
- federal tax lien: `5.12.*`
- installment and balance-due collection process: `5.14.*`, `5.19.*`
- trust fund recovery penalty: `5.7.*`, `8.25.*`, and selected `20.1.*`
- CP2000 and underreporter workflows: `4.19.*`, with selected `20.1.*` and `4.10.*`

This is exactly the kind of issue Phase 2D should solve with deterministic lexical ranking before embeddings.

## Outstanding Phase 2D Items

### 1. Add Deterministic IRM Ranking

Improve Laravel IRM search ordering so results are ranked by procedural relevance, not only by default reference ordering.

Minimum ranking signals:

- exact IRM reference match
- document-level reference match
- descendant reference match
- phrase match
- title and document-title match boosts
- body text match
- notice-code synonym expansion
- issue-family prefix boosts:
  - CP504, LT11, levy: `5.11.*`, `5.19.*`
  - lien: `5.12.*`
  - trust fund recovery penalty/TFRP: `5.7.*`, `8.25.*`, `20.1.*`
  - CP2000/underreported income: `4.19.*`, `20.1.*`, `4.10.*`

Keep this SQL/keyword based. Do not add embeddings yet.

### 2. Add Corpus Coverage Check

Add an Artisan coverage command that fails if the seeded IRM corpus is missing required procedural prefixes.

Initial required prefixes:

- `4.19`
- `5.7`
- `5.11`
- `5.12`
- `5.14`
- `5.19`
- `8.25`
- `20.1`

The command should output counts for documents and sections, ideally with a JSON option for automation.

### 3. Add Relevance Tests

Extend Laravel tests beyond "returns a result" assertions.

Needed tests:

- `levy notice` should rank `5.11.*` or closely related collection sections ahead of unrelated early IRM sections.
- `CP504` records/checklist search should map to levy/collection sources.
- `LT11` collection-risk search should map to levy/CDP collection sources.
- `CP2000` should rank underreporter/exam/penalty references such as `4.19.*` or `20.1.*`.
- `trust fund recovery penalty` should rank TFRP references such as `5.7.*` or `8.25.*`.
- exact lookup for `IRM 5.11.1.1` should return that section or a document/descendant group for that reference.
- unknown notice codes such as `CP9999` should continue returning no fabricated guidance.

### 4. Strengthen Smoke Script Assertions

Update `scripts/smoke_irs_knowledge.py` so passing means relevance, not only safety.

The smoke script should assert expected reference prefixes for non-empty cases:

- `levy_notice`: `5.11.*` or `5.19.*`
- `cp504`: `5.11.*` or `5.19.*`
- `lt11`: `5.11.*` or `5.19.*`
- `cp2000`: `4.19.*`, `20.1.*`, or `4.10.*`
- `trust_fund_recovery_penalty`: `5.7.*`, `8.25.*`, or `20.1.*`
- `unknown_notice_code`: empty source results with no-source wording

### 5. Rerun UI and Script Smoke Cases

Rerun the six required smoke cases through both the script and the UI path:

- `levy notice`
- `CP504`
- `LT11`
- `CP2000`
- `trust fund recovery penalty`
- unknown notice code, using `CP9999`

Also rerun the three user-facing prompts that exposed gaps:

- `What records should I gather for CP504?`
- `Look up IRM 5.11.1.1.`
- `Explain IRS notice CP9999.`

Expected behavior:

- CP504 records should return source-backed collection/levy records guidance.
- IRM `5.11.1.1` should return that exact section or a source-backed reference group.
- CP9999 should return a safe no-source response; that is correct behavior, not a failure.

### 6. Update Status Documentation

After Phase 2D validation passes, update:

- `docs/mcp/STATUS.md`
- `docs/mcp/PHASE_2C_VALIDATION.md`
- the smoke output under `reports/`

The docs should explicitly state whether relevance checks passed against the fully seeded local corpus and, if applicable, production EC2/RDS.

## Not Yet Ready

Do not start these yet:

- vector embeddings
- OCR
- document extraction
- IRS notice extraction MCP

The next technical decision depends on Phase 2D results:

- If deterministic ranking passes, move to Phase 3 IRS notice extraction because extracted notice data can feed the IRM tools directly.
- If deterministic ranking is still weak, add PostgreSQL full-text search ranking with `tsvector` and tuned dictionaries before considering embeddings.

## Recommended Next Step

Finish Phase 2D in this order:

1. Apply deterministic Laravel ranking and the corpus coverage command.
2. Add relevance-focused Laravel tests.
3. Upgrade the IRS smoke script to check expected IRM prefixes.
4. Run API tests, agent tests, local smoke, and UI smoke against the fully seeded local database.
5. Document pass/fail results and decide between Phase 3 notice extraction or a Phase 2E `tsvector` search-ranking pass.
