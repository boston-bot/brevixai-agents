# Brevix AI Agent Service

Phase 1 FastAPI/LangGraph orchestration service for Brevix AI.

This service does not connect to the Brevix database and does not expose raw SQL tools. Fraud and risk analysis is based only on deterministic Laravel tool endpoints under `/api/internal/agent-tools/*`.

## Local Setup

```bash
cd /Users/joe.eagan/Documents/GitHub/brevixai-agent-service
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

Expected local services:

```text
Laravel API:        http://localhost:8000
Agent service:      http://localhost:8010
```

Laravel must be configured with the same service key:

```env
BREVIX_AGENT_SERVICE_URL=http://localhost:8010
BREVIX_AGENT_SERVICE_KEY=local-dev-key
```

The agent service calls Laravel tools with:

```env
BREVIX_LARAVEL_BASE_URL=http://localhost:8000
BREVIX_LARAVEL_AGENT_TOOL_KEY=local-dev-key
```

## API

```http
POST /agent/run
Authorization: Bearer local-dev-key
```

```json
{
  "company_id": "uuid",
  "user_id": "uuid",
  "conversation_id": "optional",
  "message": "Are there any suspicious vendors this month?",
  "page_context": {
    "selected_period": "2026-05"
  }
}
```

## Graph

Phase 1 graph:

```text
START
  -> router
  -> context_loader
  -> fraud_analyzer
  -> explanation
  -> action_gate
  -> final_response
  -> END
```

The `fraud_analyzer` node calls deterministic Laravel tools. It does not run SQL and does not create alerts, cases, or other autonomous actions.

## Docker

```bash
docker build -t brevixai-agent-service .
docker run --rm -p 8010:8010 --env-file .env brevixai-agent-service
```

Or:

```bash
docker compose up --build
```
