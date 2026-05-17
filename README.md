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

## Prompt Templates

### Where prompts live

All prompt templates are in [`app/prompts/`](app/prompts/). Each template is a versioned Markdown file:

```text
app/prompts/
├── router.v1.md
├── fraud_analyzer_summary.v1.md
├── explanation.v1.md
└── action_gate.v1.md
```

The loader lives at [`app/prompts/loader.py`](app/prompts/loader.py).

### How prompt versioning works

Every prompt file is named `{name}.{version}.md`. The version is an integer (`v1`, `v2`, …). When graph nodes are initialized, all four templates are loaded from disk via `load_prompt(name, version)`. If any file is missing, the graph fails at startup — not silently at runtime.

Template variables use `{{double_brace}}` syntax and are interpolated at request time. The loader computes a SHA-256 hash of the raw file content (including frontmatter) and returns it as `prompt_hash`.

### How to create a new prompt version

1. Copy the existing file: `cp app/prompts/explanation.v1.md app/prompts/explanation.v2.md`
2. Edit `explanation.v2.md` with your changes.
3. Update the version string in `build_graph()` in [`app/graph.py`](app/graph.py):
   ```python
   _explanation_prompt = load_prompt("explanation", "v2")
   ```
4. Run tests and benchmarks. The new `prompt_hash` will appear in all trace metadata and benchmark reports, making it easy to correlate quality changes to the exact template that produced them.

**Rule: never edit an old prompt version after it has been benchmarked.** Once a benchmark report records a `prompt_hash`, that hash must remain stable so regressions can be traced back to the exact template. Create `v2` instead.

### Why prompt hashes are included in benchmark metadata

Each benchmark result in `reports/latest_benchmark_report.json` carries the `prompt_hash` of every template that was active during the run. This means:

- If benchmark quality drops between two runs, you can diff the hashes to identify which template changed.
- Rolled-back prompt versions produce identical hashes, confirming the regression was prompt-driven.
- CI enforces quality gates against the current prompt — if a prompt edit causes a regression the gate fails before merge.

### How prompt metadata appears in reports

**JSON report** (`reports/latest_benchmark_report.json`) includes a top-level `prompts_used` array:

```json
"prompts_used": [
  {
    "prompt_name": "router",
    "prompt_version": "v1",
    "prompt_hash": "3a9f2c1d..."
  },
  {
    "prompt_name": "fraud_analyzer_summary",
    "prompt_version": "v1",
    "prompt_hash": "8b4e7f0a..."
  },
  {
    "prompt_name": "explanation",
    "prompt_version": "v1",
    "prompt_hash": "c5d1e2b9..."
  },
  {
    "prompt_name": "action_gate",
    "prompt_version": "v1",
    "prompt_hash": "f7a3c8d2..."
  }
]
```

**Markdown report** (`reports/latest_benchmark_report.md`) includes a **Prompt Versions** section:

```markdown
## Prompt Versions

| Prompt                 | Version | Hash (short) |
|------------------------|---------|--------------|
| router                 | v1      | `3a9f2c1d`   |
| fraud_analyzer_summary | v1      | `8b4e7f0a`   |
| explanation            | v1      | `c5d1e2b9`   |
| action_gate            | v1      | `f7a3c8d2`   |
```

**Quality gate output** prints prompt versions before the metric checks:

```
==============================================================
Brevix AI Quality Gate
==============================================================

  Scenarios: 16/16 passed

  Prompt Versions:
    router                       v1   3a9f2c1d
    fraud_analyzer_summary       v1   8b4e7f0a
    explanation                  v1   c5d1e2b9
    action_gate                  v1   f7a3c8d2

  PASS  pass_rate                    1.000      >= 0.95
  ...
```

### How to compare reports across prompt versions

1. Generate a report before editing a prompt and save it:
   ```bash
   python scripts/run_benchmarks.py --report
   cp reports/latest_benchmark_report.json reports/before_prompt_change.json
   ```
2. Edit the prompt (bump to `v2`), update the registry, run benchmarks again:
   ```bash
   python scripts/run_benchmarks.py --report
   ```
3. Compare `prompts_used[].prompt_hash` between the two reports. A changed hash confirms which template was active when quality changed.
4. Compare quality metrics side by side to determine whether the prompt change improved or degraded results.

Old reports written before Phase 2.7 (without a `prompts_used` key) load and gate correctly — the field defaults to an empty list.

## Model Providers

The agent explanation layer is backed by a swappable model provider. The provider is selected with `BREVIX_AGENT_MODEL_PROVIDER`.

### Deterministic mode (default)

No external API calls. Rule-based explanation generation. Required for tests, CI, and benchmarks.

```env
BREVIX_AGENT_MODEL_PROVIDER=deterministic
BREVIX_AGENT_MODEL_NAME=deterministic-risk-v1
```

This is the default — no extra configuration needed.

### OpenAI mode (local development / production)

Calls the OpenAI Chat Completions API to generate explanations.

```env
BREVIX_AGENT_MODEL_PROVIDER=openai
BREVIX_AGENT_MODEL_NAME=gpt-4o
OPENAI_API_KEY=sk-...
BREVIX_AGENT_MODEL_TIMEOUT_SECONDS=30
```

Install the optional dependency first:

```bash
pip install -e ".[llm]"
```

If `OPENAI_API_KEY` is missing or empty when `model_provider=openai`, the service will refuse to start with a clear configuration error. It will never silently fall back to deterministic mode in production.

### Why CI uses deterministic mode

- Zero external API cost or latency in CI
- Perfectly reproducible outputs — benchmarks are stable across runs
- No secrets required in the GitHub Actions environment

### Required env vars for real LLM mode

| Variable | Required for OpenAI | Default |
|----------|--------------------|---------| 
| `BREVIX_AGENT_MODEL_PROVIDER` | yes (`openai`) | `deterministic` |
| `BREVIX_AGENT_MODEL_NAME` | yes | `deterministic-risk-v1` |
| `OPENAI_API_KEY` | yes | _(empty)_ |
| `BREVIX_AGENT_MODEL_TIMEOUT_SECONDS` | no | `30` |

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

## CI Workflow

The workflow at [`.github/workflows/benchmark-quality-gate.yml`](.github/workflows/benchmark-quality-gate.yml) runs automatically on every pull request and every push to `main`.

### What the workflow does

1. Checks out the repo and sets up Python 3.10.
2. Installs all dependencies with `pip install -e ".[dev]"`.
3. Runs unit tests (report generation, quality gate logic) — fast, no benchmark run.
4. Runs the full fraud benchmark suite and writes `reports/latest_benchmark_report.json` and `reports/latest_benchmark_report.md`.
5. Enforces the quality gate against the generated report.
6. Uploads the `reports/` directory as a build artifact named `benchmark-reports-<run-id>` — available even when the gate fails.

### What causes CI failure

The pipeline fails (exit 1) when any quality gate threshold is breached:

| Metric | Threshold |
|--------|-----------|
| `pass_rate` | < 0.95 |
| `severity_accuracy` | < 0.95 |
| `evidence_completeness_avg` | < 0.90 |
| `false_positive_pass_rate` | < 0.95 |
| `hallucination_failure_count` | > 0 |
| `average_latency_ms` | > 500 ms |

Unit test failures also block the pipeline before benchmarks run.

### Where benchmark reports are uploaded

Go to the failed workflow run on GitHub → **Summary** → **Artifacts** → `benchmark-reports-<run-id>`. The artifact contains:

```text
latest_benchmark_report.json   # machine-readable metrics
latest_benchmark_report.md     # human-readable breakdown with failed checks
```

Reports are uploaded on every run, including failures, so you can inspect what regressed.

### How to reproduce CI locally

```bash
source .venv/bin/activate

# Step 1: unit tests
pytest tests/ --ignore=tests/test_evals.py -q

# Step 2: benchmarks + report
python scripts/run_benchmarks.py --report

# Step 3: quality gate
python scripts/quality_gate.py --report-json reports/latest_benchmark_report.json
```

No GitHub secrets are required. The benchmark suite uses the deterministic model provider and makes no external API calls.
