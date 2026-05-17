# Brevix AI Agent Service

Phase 1 FastAPI/LangGraph orchestration service for Brevix AI.

This service does not connect to the Brevix database and does not expose raw SQL tools. Fraud and risk analysis is based only on deterministic Laravel tool endpoints under `/api/internal/agent-tools/*`.

## Local Setup

```bash
cd brevixai-agents
python3 -m venv .venv
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

## Benchmarks & Quality Gates

All benchmark and quality gate commands require the virtualenv to be active:

```bash
source .venv/bin/activate
```

### Run benchmarks

Run the full fraud scenario benchmark suite and print a per-scenario report:

```bash
python scripts/run_evals.py
```

### Generate reports

Run benchmarks and write structured JSON and Markdown reports to `reports/`:

```bash
python scripts/run_benchmarks.py --report
```

Output files:

```text
reports/latest_benchmark_report.json
reports/latest_benchmark_report.md
```

### Run the quality gate locally

Check that benchmark results meet the minimum quality thresholds. Exits 0 on pass, 1 on fail.

**Run benchmarks then check gates in one step:**

```bash
python scripts/quality_gate.py
```

**Check gates against an existing report (faster — skips re-running benchmarks):**

```bash
python scripts/quality_gate.py --report-json reports/latest_benchmark_report.json
```

**Override individual thresholds:**

```bash
python scripts/quality_gate.py \
  --report-json reports/latest_benchmark_report.json \
  --min-pass-rate 1.0 \
  --min-severity-accuracy 0.95 \
  --min-evidence-completeness 0.90 \
  --min-false-positive-pass-rate 0.95 \
  --max-hallucination-failures 0 \
  --max-average-latency-ms 500
```

Default thresholds:

| Metric | Default |
|--------|---------|
| `pass_rate` | >= 0.95 |
| `severity_accuracy` | >= 0.95 |
| `evidence_completeness_avg` | >= 0.90 |
| `false_positive_pass_rate` | >= 0.95 |
| `hallucination_failure_count` | <= 0 |
| `average_latency_ms` | <= 500 ms |

### Run benchmark tests in CI

Unit tests only (fast, no benchmark run):

```bash
pytest tests/test_report.py tests/test_quality_gate.py -v
```

Full benchmark suite as pytest (one test per scenario):

```bash
pytest tests/test_evals.py -v
```

### Suggested CI command

```bash
python scripts/run_benchmarks.py --report \
  && python scripts/quality_gate.py --report-json reports/latest_benchmark_report.json
```

This generates a fresh report and then enforces the quality gate in a single CI step. The pipeline fails if any threshold is breached.
