# Phase 3 — IRS Notice Extraction

Date: 2026-05-31

Status: Complete

## Goal

Add a notice extraction tool that accepts raw IRS notice text, identifies the notice type and key risk fields via the existing `IrsTaxNoticeService`, and automatically chains into the IRM knowledge tools to return source-backed procedural sections in a single call.

Extracted notice fields feed directly into the tools built in Phase 2:
- `notice_type` → `explainNoticeType()` → IRM sections for that notice code
- `risk_level` and `deadline_days` → surfaced in the agent's answer

## Scope

**In scope:**
- Text-based notice extraction (pasted notice content)
- New internal agent-tool endpoint `POST /api/internal/agent-tools/irs/notice/extract`
- New `IrsNoticeExtractionService` combining `IrsTaxNoticeService` + `IrmKnowledgeService`
- New `irs_notice_extract` MCP tool
- Router detection for notice text submission (long pasted notice body)
- Answer synthesis for extraction results

**Out of scope (not yet):**
- PDF parsing / OCR
- File uploads for notices
- Storing extracted notices in the database
- Batch extraction

## Architecture

```
User pastes notice text
        ↓
irs_procedural.py: _is_notice_text_submission()
        ↓
irs_notice_extract tool (new)
        ↓
LaravelToolClient.irs_notice_extract() → POST /api/internal/agent-tools/irs/notice/extract
        ↓
IrsNoticeExtractionService.extract()
   ├─ IrsTaxNoticeService.interpretNotice()  → LLM extraction
   │     returns: notice_type, deadline_days, required_action, risk_level, key_amount, summary
   └─ IrmKnowledgeService.explainNoticeType() → IRM section search
         returns: IRM sections for the extracted notice_type
        ↓
Combined payload → synthesize_irs_answer() → agent answer with irm_reference + disclaimer
```

## Endpoint

`POST /api/internal/agent-tools/irs/notice/extract`

Request body:
```json
{
  "text": "<raw notice text, 20–10000 chars>",
  "limit": 5
}
```

Response:
```json
{
  "status": "ok",
  "notice_type": "CP504",
  "deadline_days": 30,
  "deadline_description": "30-day window from notice date",
  "required_action": "File Form 9465 or pay in full to stop levy action.",
  "risk_level": "critical",
  "key_amount": 5000.00,
  "summary": "...",
  "irm_search_topic": "levy notice intent to levy balance due collection",
  "results": [ ...IRM sections... ],
  "disclaimer": "..."
}
```

## Router Detection

`classify_irs_tool_request()` routes to `irs_notice_extract` when the message:
- Contains a notice text submission trigger phrase ("my notice says", "i received a notice", "notice reads", "here is my notice", etc.), OR
- Exceeds 300 characters AND contains an IRS anchor term

This lets short code questions ("What is CP504?") continue using the faster `irs_notice_type` path while pasted notice bodies go to full extraction.

## Files Changed

**brevixai-api:**
- `app/Services/IrsNoticeExtractionService.php` (new)
- `app/Http/Controllers/Internal/IrmKnowledgeController.php` (add `extractNotice` action)
- `routes/api.php` (add POST route)
- `tests/Feature/IrsNoticeExtractionToolTest.php` (new)

**brevixai-agents:**
- `app/tools/laravel.py` (add `_post()`, add `irs_notice_extract()`)
- `mcp_servers/brevix_intelligence/tools/irs_knowledge.py` (add `extract_irs_notice()`)
- `mcp_servers/brevix_intelligence/server.py` (register `extract_irs_notice_tool`)
- `app/irs_procedural.py` (add `"irs_notice_extract"` to ToolName, routing, synthesis)
- `mcp_servers/brevix_intelligence/tests/test_irs_knowledge.py` (add test)

## Completion Notes

Completed on 2026-05-31.

Agent-side verification includes:
- `tests/test_irs_notice_extraction.py`
- `tests/test_laravel_tool_client.py`
- `mcp_servers/brevix_intelligence/tests/test_irs_knowledge.py`
- `mcp_servers/brevix_intelligence/tests/test_server.py`

The extraction path is text-first. PDF/OCR, upload handling, persistence, and batch processing remain future work.
