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

See the [Benchmark History & Comparison](#benchmark-history--comparison) section below for the full comparison workflow.

Old reports written before Phase 2.7 (without a `prompts_used` key) load and gate correctly — the field defaults to an empty list.

## Benchmark History & Comparison

### Saving timestamped benchmark history

Pass `--history` alongside `--report` to write a timestamped copy of every report to `reports/history/`:

```bash
python scripts/run_benchmarks.py --report --history
```

Output:

```text
reports/latest_benchmark_report.json        ← always overwritten (latest)
reports/latest_benchmark_report.md
reports/history/benchmark_report_20260517_143052.json   ← timestamped copy
reports/history/benchmark_report_20260517_143052.md
```

The timestamp is derived from the report's `generated_at` field in `YYYYMMDD_HHMMSS` format. Accumulating history files lets you compare any two runs at any point in time.

### Comparing two reports

```bash
python scripts/compare_benchmark_reports.py \
  --base  reports/history/benchmark_report_20260515_100000.json \
  --current reports/latest_benchmark_report.json
```

With optional file output:

```bash
python scripts/compare_benchmark_reports.py \
  --base  reports/history/benchmark_report_20260515_100000.json \
  --current reports/latest_benchmark_report.json \
  --output-json reports/comparison.json \
  --output-md  reports/comparison.md
```

### How to interpret the comparison output

**Console summary:**

```
==============================================================
Brevix AI Benchmark Comparison
==============================================================

  Base:    2026-05-15T10:00:00+00:00
  Current: 2026-05-17T14:30:52+00:00

  Metric Deltas
  ----------------------------------------------------------
  BETTER   pass_rate                       0.9375 -> 1.0  (+0.0625)
  SAME     severity_accuracy               1.0  (no change)
  WORSE    average_latency_ms              4.7 -> 8.5  (+3.8)

  Scenario Changes
  ----------------------------------------------------------
  Newly failed  (1): split_payments_under_threshold
  Newly passing (2): vendor_concentration, duplicate_invoice

  Prompt Changes
  ----------------------------------------------------------
  SAME     action_gate                     d7f3a8c2
  CHANGED  explanation                     c5d1e2b9 -> e8b1f4c7
  SAME     fraud_analyzer_summary          8b4e7f0a
  SAME     router                          3a9f2c1d

==============================================================
Summary: 1 improved, 1 degraded | 1 new failure(s), 2 new pass(es) | 1 prompt change(s)
(Informational only — does not affect CI pass/fail)
==============================================================
```

**Metric direction labels:**

| Label | Meaning |
|-------|---------|
| `BETTER` | Metric moved in a positive direction (higher for rates, lower for latency/failures) |
| `WORSE` | Metric moved in a negative direction |
| `SAME` | Change smaller than 0.000001 — treated as stable |

**Prompt Changes block:** `CHANGED` means the SHA-256 hash of the template file is different between runs. Use this to confirm whether a quality shift was prompt-driven.

### Typical workflow for a prompt change

```bash
# 1. Save a baseline before editing
python scripts/run_benchmarks.py --report --history

# 2. Edit the prompt (create v2, bump version in build_graph)

# 3. Run again and save new history entry
python scripts/run_benchmarks.py --report --history

# 4. Compare
python scripts/compare_benchmark_reports.py \
  --base  reports/history/benchmark_report_<before_ts>.json \
  --current reports/latest_benchmark_report.json \
  --output-md reports/comparison.md
```

The `CHANGED` flag in the Prompt Changes section confirms exactly which template hash changed, and the Metric Deltas section shows whether the change helped or hurt.

### Why comparison is informational for now

The comparison script always exits 0 (except when a file cannot be loaded). Degradations are visible in the output but do not block CI. The quality gate (`quality_gate.py`) enforces absolute thresholds; the comparison tool provides relative context that is most useful during prompt iteration and code review.

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

## Coverage Matrix

The coverage matrix shows which fraud categories, risk types, severities, and tags are exercised by the benchmark suite. Use it to spot gaps before adding new scenarios.

### Generating the coverage matrix

```bash
python scripts/generate_coverage_matrix.py
```

Output files:

```text
reports/coverage_matrix.json   # machine-readable counts and quality checks
reports/coverage_matrix.md     # human-readable tables and gap recommendations
```

CI generates both files automatically on every run and uploads them with the benchmark artifact.

### Interpreting coverage gaps

The Markdown report includes a **Recommended Gaps to Fill Next** section that flags:

| Signal | Meaning |
|--------|---------|
| `Tag X has 0 scenarios` | No scenario exercises this fraud pattern label — add one |
| `Severity X has no coverage` | No scenario tests this severity level — add one |
| `Category X has only 1 scenario` | Thin coverage — a single scenario is a weak signal for a whole category |
| `Duplicate scenario IDs` | Two entries share the same `id` — one must be renamed |
| `Missing evidence patterns` | A scenario has no `expected_evidence_patterns` — evidence completeness evaluation is skipped |
| `Missing false-positive guardrails` | A scenario has no `false_positive_guardrails` — false-positive detection is disabled |

The **Data Quality Checks** table shows PASS/FAIL for each check. Any FAIL blocks clean benchmark interpretation.

## Scenario Authoring & Validation (Phase 2.12)

To ensure that the benchmark suite remains high-quality and consistent, all benchmark scenarios (including those in `datasets/fraud_benchmarks.json`) must follow strict schema and quality rules. 

### How to add a new benchmark scenario

1. **Locate the Scenario Template**: Use [datasets/templates/fraud_scenario_template.json](file:///Users/joe.eagan/Documents/GitHub/brevixai-agents/datasets/templates/fraud_scenario_template.json) as a starting point.
2. **Draft your Scenario**: Copy the template structure, fill in all required fields (under realistic conditions/fakes), and place the new entry inside the array in `datasets/fraud_benchmarks.json`.
3. **Validate your changes**: Run the local validator CLI before committing:
   ```bash
   python scripts/validate_benchmark_dataset.py
   ```
4. **Run coverage checks**: Run `python scripts/generate_coverage_matrix.py` and inspect `reports/coverage_matrix.md` to verify that your scenario closes actual gaps.
5. **Run the benchmarks**: Ensure the new scenario passes execution and evaluation without regressing other scenarios:
   ```bash
   python scripts/run_benchmarks.py --report
   ```

---

### Dataset Quality Rules

A benchmark scenario is considered high-quality only if it satisfies all of the following rules:

1. **12 Required Fields**:
   - `scenario_id`: A unique string identifier.
   - `title`: A human-friendly title for UI and reporting.
   - `category`: Logical grouping (e.g., `accounts_payable`, `vendor_management`, `payroll`, `accounting`).
   - `risk_type`: Specific fraud pattern under test.
   - `severity`: Ground-truth risk severity level (`info`, `low`, `medium`, `high`, `critical`).
   - `tags`: List of searchable labels (cannot be empty).
   - `input_prompt`: The simulated user message.
   - `expected_findings`: List of lowercase key phrases that the agent must mention in its findings text.
   - `expected_severity`: Expected severity output by the agent (must match ground-truth severity).
   - `expected_evidence_patterns`: Structural patterns to verify agent evidence completeness.
   - `expected_recommended_action`: The expected action type recommendations.
   - `false_positive_guardrails`: Keyword terms characteristic of other fraud patterns to prevent false positives.
   
2. **Format and Uniqueness Rules**:
   - `scenario_id` must use lowercase `snake_case` (matching `^[a-z0-9_]+$`).
   - `scenario_id` (and the `id` alias) must be unique across the entire dataset.
   - Ground-truth and expected severity must be one of: `info`, `low`, `medium`, `high`, `critical` (case-insensitive).
   
3. **Non-Empty Checks**:
   - `tags` must be a non-empty list of non-empty strings.
   - `expected_findings` must be a non-empty list of non-empty strings.
   - `expected_evidence_patterns` must be non-empty list/dict structure.
   - `false_positive_guardrails` must be non-empty list/dict structure.

4. **Security & PII Shielding (Prohibited Sensitive Raw Payloads)**:
   To prevent real-world private data from leaking into git history or benchmark logs, no plain, raw, or unmasked sensitive credentials or PII fields are allowed in tool fixtures, seeded companies, seeded vendors, or seeded transactions. The validator CLI scans the entire scenario JSON recursively to block keys matching:
   `ssn`, `social_security_number`, `password`, `api_key`, `apikey`, `secret`, `secret_key`, `private_key`, `routing_number`, `bank_routing_number`, `credit_card`, `card_number`, `cvv`, `pin`.

---

### How to validate before committing

The CLI validator `scripts/validate_benchmark_dataset.py` checks both single scenario files and the entire dataset:

```bash
# Validate the default dataset (datasets/fraud_benchmarks.json)
python scripts/validate_benchmark_dataset.py

# Validate a specific file or draft scenario
python scripts/validate_benchmark_dataset.py datasets/templates/fraud_scenario_template.json
```

It outputs clear, color-coded details of any quality breaches and exits with code `0` if all checks pass, and `1` if any fail. This validation is run in GitHub Actions on every pull request and push to `main` before benchmark execution starts, blocking any non-compliant additions.

---

## Scenario Metadata & Selective Runs

Each scenario in `datasets/fraud_benchmarks.json` carries structured metadata that enables targeted local runs without modifying CI.

### Scenario metadata fields

Every scenario entry requires these fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `scenario_id` | string | yes | Unique scenario identifier in lowercase snake_case |
| `title` | string | yes | Descriptive title for reporting |
| `category` | string | yes | Logical grouping (e.g. `accounts_payable`, `vendor_management`) |
| `risk_type` | string | yes | Specific fraud pattern (e.g. `duplicate_invoice`, `ghost_vendor`) |
| `severity` | string | yes | `critical`, `high`, `medium`, `low`, or `info` |
| `tags` | list of strings | yes | Searchable labels — must be a non-empty list of strings |

The dataset loader validates fields at load time. A missing or malformed field raises `DatasetValidationError` before any scenario runs.

### Available categories

| Category | Scenarios |
|----------|-----------|
| `accounts_payable` | duplicate_invoice, split_payments_under_threshold, vendor_concentration, round_dollar_payments, unusual_refund_activity, weekend_after_hours_payment, approval_threshold_splitting, high_risk_vendor_concentration_over_time |
| `vendor_management` | ghost_vendor, employee_vendor_overlap, shared_bank_account_multiple_vendors, vendor_paid_before_onboarding, duplicate_vendor_name_variation |
| `payroll` | payroll_anomaly |
| `accounting` | reconciliation_mismatch |

### Available tags

| Tag | Meaning |
|-----|---------|
| `vendor` | Involves a vendor record or vendor-level risk |
| `payroll` | Involves payroll disbursements |
| `reconciliation` | Involves ledger or bank reconciliation |
| `duplicate` | Involves duplicate invoices or duplicate vendor entries |
| `threshold` | Involves approval threshold evasion or splitting |
| `payments` | Involves payment transaction patterns |
| `after_hours` | Involves weekend or after-hours processing timing |
| `onboarding` | Involves vendor onboarding controls |
| `entity_graph` | Involves relationships between entities (vendors, employees, bank accounts) |
| `false_positive_guardrail` | Reserved for scenarios that specifically test false-positive suppression |

### Selective run examples

Run only vendor management scenarios:

```bash
python scripts/run_benchmarks.py --report --category vendor_management
```

Run only high-severity scenarios:

```bash
python scripts/run_benchmarks.py --report --severity high
```

Run all scenarios tagged with `vendor`:

```bash
python scripts/run_benchmarks.py --report --tag vendor
```

Run scenarios tagged with both `vendor` AND `entity_graph` (AND logic):

```bash
python scripts/run_benchmarks.py --report --tag vendor --tag entity_graph
```

Run high-severity payment scenarios:

```bash
python scripts/run_benchmarks.py --report --severity high --tag payments
```

Run a specific risk type:

```bash
python scripts/run_benchmarks.py --report --risk-type threshold_evasion
```

Multiple filters always combine with AND — a scenario must match every specified filter to be included.

### Filtered report output

When filters are active, reports include an **Active Filters** section:

```markdown
## Active Filters

| Filter | Value |
|--------|-------|
| severity | high |
| tags | vendor, entity_graph |

Scenarios run: 4 / 15 (11 skipped)
```

The JSON report includes the same data as top-level fields:

```json
{
  "active_filters": { "severity": "high", "tags": ["vendor"] },
  "skipped_scenario_count": 11,
  "total_scenarios": 4,
  ...
}
```

The `total_scenarios` field always reflects the number of scenarios actually run (after filtering), not the full dataset size.

### Recommended CI vs. local workflow

**CI (full suite, no filters):**

```bash
python scripts/run_benchmarks.py --report \
  && python scripts/quality_gate.py --report-json reports/latest_benchmark_report.json
```

**Local — targeted smoke test during development:**

```bash
# Fast check: vendor management scenarios only
python scripts/run_benchmarks.py --report --category vendor_management

# Focus on the risk type you're working on
python scripts/run_benchmarks.py --report --risk-type duplicate_invoice

# Run high-severity scenarios before a prompt change
python scripts/run_benchmarks.py --report --severity high --history
```

Filtered runs do not overwrite `reports/latest_benchmark_report.json` in a way that breaks CI — they write the same file path but CI always regenerates fresh from the full unfiltered dataset.

### Quality gate with filters

The quality gate supports the same filter flags for fresh benchmark runs:

```bash
# Gate check on vendor scenarios only (fresh run)
python scripts/quality_gate.py --tag vendor

# Gate check against an existing filtered report
python scripts/quality_gate.py --report-json reports/latest_benchmark_report.json
```

When `--report-json` is provided, filter flags are ignored — the gate evaluates whatever was captured in the report.

## Benchmark Snapshot

### What BENCHMARK_SNAPSHOT.md is

`reports/BENCHMARK_SNAPSHOT.md` is a polished, human-readable summary generated from the latest benchmark report. It is designed to be read without tooling, attached to release notes, or shared in a PR description.

It includes:
- Service version and generation timestamp
- **Release readiness status** — `READY` or `REVIEW REQUIRED` based on default quality gate thresholds
- Quality metrics table with threshold and pass/fail for each metric
- Dataset coverage: total scenarios run and categories covered
- Active filters if the report was produced by a filtered run
- Slowest scenarios
- Prompt versions and short hashes
- Known gaps

### When it is generated

CI generates `BENCHMARK_SNAPSHOT.md` automatically on every PR and push to `main`, immediately after the quality gate step. It is included in the `benchmark-reports-<run-id>` artifact alongside the JSON and Markdown reports.

If the quality gate fails, the snapshot is still generated (with `REVIEW REQUIRED` status) so reviewers can read a clear human summary of what failed.

### How to generate it locally

```bash
python scripts/generate_benchmark_snapshot.py
```

This reads `reports/latest_benchmark_report.json` and writes `reports/BENCHMARK_SNAPSHOT.md`. Run the benchmarks first:

```bash
python scripts/run_benchmarks.py --report
python scripts/generate_benchmark_snapshot.py
```

With a custom report or output path:

```bash
python scripts/generate_benchmark_snapshot.py \
  --report-json reports/history/benchmark_report_20260517_143052.json \
  --output /tmp/snapshot.md
```

### How to attach it to release notes

1. Download the `benchmark-reports-<run-id>` artifact from the CI run that corresponds to the release commit.
2. Open `BENCHMARK_SNAPSHOT.md` — it is ready to paste or attach.
3. Copy the **Release Readiness** and **Quality Metrics** sections into your release notes or GitHub Release description.

The snapshot is self-contained and does not require access to the benchmark tooling to read.

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
