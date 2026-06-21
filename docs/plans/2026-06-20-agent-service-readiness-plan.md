# Brevix Agent Service Readiness Plan

**Repository:** `brevixai-agents`  
**Review date:** 2026-06-20  
**Status:** Planning only — no implementation work authorized by this plan  
**Related plans:**

- `../brevixai-api/docs/plans/2026-06-20-backend-readiness-plan.md`
- `../brevixai/docs/plans/2026-06-20-frontend-readiness-plan.md`

**Launch direction:** CPA Investigation Workspace / Evidence Builder  
**First vertical:** Evidence-backed Vendor & Payment Review  
**Launch users:** business owner and invited CPA/advisor reviewer in one client workspace

## Executive conclusion

This repository has the right strategic role: a private, bounded orchestration and explanation layer that calls Laravel tools rather than databases, creates no autonomous sensitive action, and returns user-facing explanation/synthesis. Its vendor/payment workflows, deterministic benchmarks, action gate, prompt versioning, SSE progress, and observability scaffolding are a strong base.

It is **not release-ready for the chosen vertical**. The immediate blockers are:

1. The declared current baseline has a red full test suite: **592 passed, 1 failed**. The `ghost_vendor` benchmark is diverted into the new fraud-discovery path, whose fixture lacks the required playbook method; the expected finding, severity, and evidence are lost.
2. Laravel passes selected `business_profile_id`, but the FastAPI request model, graph state, and Laravel tool headers discard it. Tool calls cannot be proven to remain inside the selected client profile.
3. The baseline automatically persists all returned agent findings to Laravel but does not receive canonical finding identities, materialization results, or conflicts. Its generic finding model lacks stable source identity and canonical evidence/action fields.
4. The current agent evidence model requests documents but cannot reliably tell which source evidence, freshness, coverage, reviewer notes, or decisions actually exist in Laravel.

The agent must not expand from a bounded explanation layer into a general autonomous investigator. Launch work should make it a reliable companion to the canonical Laravel finding and investigation modules.

## Architecture and responsibility map

```text
brevixai
  -> Laravel (auth, selected workspace/profile, durable facts, evidence, findings,
             investigations, reviewer decisions, approvals, audit trail)
       -> brevixai-agents (private intent routing, deterministic workflow selection,
                           explanation, synthesis, recommendation wording)
            -> Laravel internal tools only
```

### Confirmed responsibilities

| Responsibility | Owner |
| --- | --- |
| Identity, tenancy/profile access, source data, canonical findings/evidence, mutations, reviewer authority, packages | Laravel |
| Guided interaction, layout, data-state presentation, reviewer controls | Frontend |
| Intent selection, controlled tool use, deterministic-workflow explanation, bounded synthesis, action recommendation wording | Agent service |
| Any sensitive execution | Laravel only, following a human approval and server-side authorization |

The agent can persist a source-backed canonical finding only through Laravel's explicitly approved materialization route. It may not decide that a generic chat response is a durable investigation record.

## Approved first-vertical behavior

For Vendor & Payment Review, the agent can help a user understand a deterministic Laravel result:

```text
Laravel source coverage + deterministic vendor/payment signals
  -> agent selects an approved vendor/payment workflow
  -> agent explains cited signals, scope limitations, and requested evidence
  -> Laravel returns canonical finding/investigation/reviewer-decision state
  -> frontend renders the result and offers only role-authorized actions
```

The agent must not:

- call a database directly or infer source records it did not receive;
- state that fraud occurred, that a payment is unauthorized, or that professional advice was given;
- create an investigation, package, review decision, or sensitive action outside Laravel authorization;
- convert an education/RAG answer into a durable finding without source-backed materialization;
- hide partial-tool failure, missing evidence, or selected-profile ambiguity.

## Current-state evidence

### Strengths to preserve

- The tool client exposes named Laravel methods rather than arbitrary URL/SQL execution: `app/tools/laravel.py`.
- Vendor risk, reconciliation, entity relationship, aggregate risk, and payment-analysis paths exist in `app/graph.py`; vendor verification includes evidence requests and scope limitations in `app/vendor_verification_workflow.py`.
- Investigation synthesis correlates only shared evidence anchors: `app/investigation_synthesis.py`.
- The agent gates sensitive recommendation types and never executes them: `app/graph.py`, `app/prompts/action_gate.v2.md`.
- FastAPI has bearer authentication, production CORS/config checks, SSE heartbeats, request/tool timing, optional LangSmith metadata, Docker, Compose, EC2 deployment automation, and ECS starter configuration.
- A deterministic 21-scenario benchmark covers vendor/payment patterns, duplicate invoices, threshold evasion, reconciliation, relationship signals, and false-correlation suppression.

### Release-blocking gaps

| Severity | Finding | Evidence |
| --- | --- | --- |
| Critical | Full suite is red: `ghost_vendor` fails after new fraud-discovery routing requests a playbook method absent from the benchmark fake. | `tests/test_evals.py`, `app/graph.py`, `app/fraud_discovery_workflow.py` |
| Critical | Selected business profile is not represented in `AgentRunRequest`, graph state, or Laravel-tool headers. | `app/models.py`, `app/main.py`, `app/tools/laravel.py` |
| Critical | Generic agent findings are automatically persisted but lack stable canonical source keys and do not return canonical IDs/materialization outcome. | `app/main.py`, `app/models.py`, Laravel `AgentToolController` |
| High | Guided-intake tool methods target Laravel routes not in Laravel's registered agent tool set. | `app/graph.py`, `app/tools/laravel.py`, Laravel `AgentToolRegistry` |
| High | Action type lists diverge between agent configuration/prompts and Laravel's supported executor actions. | `app/config.py`, `app/prompts/action_gate.v2.md`, `app/graph.py`, Laravel action executor/registry |
| High | Evidence requests are hard-coded as missing and are not reconciled with canonical evidence items, source coverage/freshness, reviewer notes, or decisions. | `app/vendor_verification_workflow.py`, `app/graph.py` |
| High | Fraud-discovery/RAG is in the intended baseline but has incomplete fixture and contract coverage. It should not silently replace deterministic vendor analysis. | `app/fraud_discovery_workflow.py`, `app/prompts/fraud_discovery_v1.md` |
| High | The graph accepts `ORCHESTRATOR_CHECKPOINTER` configuration but has no actual checkpointer or interrupt/resume path. | `app/config.py`, `app/graph.py` |
| Medium | Latest benchmark report is from 2026-05-23, runs deterministic fixtures, and states it does not measure real-model latency, live Laravel evidence, or nuanced reasoning quality. | `reports/latest_benchmark_report.md` |
| Medium | Product/readiness documents conflict on Phase 5 status and the broader redesign remains marked draft. | `docs/mcp/STATUS.md`, `docs/superpowers/2026-06-12-investigation-platform-redesign.md` |
| Medium | Some relational/control analysis requires production identifiers/fields the backend does not yet provide. | `docs/mcp/STATUS.md` |

## Readiness assessment

| Dimension | Status | Consequence |
| --- | --- | --- |
| Orchestration boundary | Strong foundation | Keep the agent private and Laravel-tool-only. |
| Vendor/payment explanation | Partial | Useful deterministic workflow exists, but it cannot yet cite a complete Laravel-owned evidence state. |
| Selected-profile tenancy | Blocked | Owner/advisor work in one selected client profile is unsafe to claim until propagated and tested end to end. |
| Canonical persistence | Blocked | Automatic generic finding writes can duplicate, lack provenance, or fail without a frontend-visible outcome. |
| Guided intake | Blocked | Agent assumes tool routes that Laravel does not advertise and frontend/server onboarding contracts disagree. |
| Human approval | Good baseline, contract drift present | Sensitive recommendations are gated, but action vocabulary must match Laravel exactly. |
| Evaluation | Blocked | Current full suite is red; existing benchmark evidence is stale and fixture-bound. |
| Durable workflows | Not implemented | Appropriate for short requests only; do not claim resumable human-in-the-loop orchestration. |
| Operations | Partial | Deployment artifacts and health checks exist; deployment target, runbook authority, real-model SLOs, and alerting remain unverified. |

## Sequenced agent-service plan

### Phase 0 — stabilize the declared baseline

1. Classify all dirty and untracked work as part of the intended baseline, including fraud-discovery code, prompts, playbooks, MCP documents, and fixtures.
2. Fix the `ghost_vendor` evaluation regression. Decide explicitly whether it is a deterministic Vendor & Payment Review scenario or an education/RAG scenario; do not allow keyword routing to silently change its meaning.
3. Require the full test suite, deterministic benchmark run, and quality gate to pass from the same commit before feature work proceeds.
4. Regenerate dated benchmark/coverage reports only after the suite is green; record model provider, fixture source, prompt hashes, and command.

**Exit criteria:** the intended baseline is documented; full tests, benchmark, and quality gate pass; every benchmark scenario asserts the intended workflow and failure behavior.

### Phase 1 — establish the cross-repository investigation-run contract

**Goal:** An agent request can only use the same selected client context that Laravel authorized.

1. Define a versioned contract owned by Laravel and consumed by the agent: run identity, company, business profile, authenticated user, reviewer role, selected review period, source coverage/freshness, enabled tools, and response/degradation semantics.
2. Propagate the selected business profile through `AgentRunRequest`, graph state, every Laravel-tool call, traces, and tests. Reject an ambiguous/missing profile rather than defaulting silently.
3. Reconcile the contract across Laravel tool registry, Python tool client, FastAPI request/response models, SSE payloads, and frontend Rex consumers.
4. Add an executable parity gate with owner, advisor, cross-workspace, cross-profile, and stale/invalid context cases.

**Exit criteria:** every enabled tool receives the selected profile; a request cannot fall back to an unintended client; both repositories fail CI if their contract diverges.

### Phase 2 — make canonical finding persistence selective and idempotent

**Goal:** Only durable, source-backed signals become canonical findings.

1. Define which agent outputs are explanation only, which are recommendation only, and which qualify for materialization as a canonical finding.
2. For materialized findings, require Laravel-owned stable source keys, reason codes, evidence references, scope limitations, suggested records, recommended action, and agent/run lineage.
3. Return canonical finding IDs, materialization state, and safe conflict/idempotency outcomes to the agent and frontend.
4. Ensure repeat streams/retries do not duplicate records; test synchronous, streamed, partial-tool, and retry paths.
5. Do not dual-write legacy alerts in the selected vertical.

**Exit criteria:** each persisted vendor/payment finding is traceable to durable source evidence and appears once in the canonical Findings queue; generic chat prose remains non-durable.

### Phase 3 — make Vendor & Payment Review evidence-aware

**Goal:** Explanations describe what the system actually knows, what it does not know, and what record would reduce uncertainty.

1. Replace hard-coded evidence gaps with Laravel-owned evidence availability, coverage period, freshness, provenance, and reviewer-decision context.
2. Support only the launch evidence types confirmed by product and backend plans; display unavailable controls/relational insights as unavailable, not negative findings.
3. Require every agent explanation to distinguish deterministic signal, cited source evidence, scope limitation, education/RAG context, and human reviewer decision.
4. Define the reviewer-oriented output for the selected vertical: why flagged, evidence list, limitations, missing records, suggested next review step, and link to canonical finding/investigation.

**Exit criteria:** an owner and advisor receive a response that agrees with Laravel evidence state; no explanation implies a fact the selected evidence cannot support.

### Phase 4 — contain education/RAG and advanced workflows

**Goal:** Preserve discovery value without contaminating the evidence-backed review path.

1. Separate education/RAG intent from source-backed Vendor & Payment Review in routing, output vocabulary, persistence policy, and evaluation fixtures.
2. Require source citations, retrieval failure behavior, source quality/provenance, and no-materialization policy for education-only responses.
3. Add regression fixtures for overlapping phrases such as “ghost vendor,” duplicate payments, and generic fraud concerns so deterministic evidence review retains precedence when company data exists.
4. Keep relational graph, approval/document control, and multi-step fraud playbooks disabled or explicitly limited until Laravel payload smoke gates verify the required production fields.

**Exit criteria:** RAG cannot suppress or replace a deterministic company-data workflow; any education response tells the user what evidence is needed and does not create a finding by itself.

### Phase 5 — make safety, operations, and evaluation releaseable

**Goal:** Support a reliable, observable short-lived analysis run for the chosen vertical.

1. Normalize action vocabulary and approval semantics with Laravel; actions unsupported by Laravel must be rejected before they reach user-facing output.
2. Surface degraded tools, unavailable evidence, persistence failures, and timeouts in a structured response that frontend users can understand and operators can alert on.
3. Add real-model evaluation for bounded explanation quality, citation fidelity, misleading-claim suppression, latency, and deterministic-versus-RAG routing. Deterministic benchmarks remain necessary but are not sufficient.
4. Decide whether durable checkpoint/resume is required. If not, document the agent as a short-lived analysis module and leave long-lived review state in Laravel. If yes, design a durable checkpoint, resume, authorization, and recovery module before enabling it.
5. Verify target deployment, secrets, health endpoint, logging, alert thresholds, dependency patching, and rollback ownership. Resolve the multiple deployment artifacts into one authoritative production path.

**Exit criteria:** a production-like run produces traceable output, clear degraded state, supported actions only, current evaluation evidence, and an owner-approved operational runbook.

## Candidate deepening opportunities

These are candidates, not implementation instructions. No new interface should be designed until the Laravel contract and product decisions for the relevant phase are approved.

1. **Selected-review-context module**
   - **Files:** `app/models.py`, `app/main.py`, `app/graph.py`, `app/tools/laravel.py`, Laravel agent middleware/controllers.
   - **Problem:** selected profile, reviewer identity, tool authorization, and trace context are scattered; a required tenancy fact is currently lost at the agent seam.
   - **Solution to explore:** make one deep module own propagation, validation, and trace-safe representation of the authorized review context.
   - **Benefits:** more leverage for every workflow and strong locality for tenancy bugs. Deletion test: removing this module would force every workflow/tool caller to rebuild security context, so it earns its keep once it owns the complete invariant.

2. **Canonical finding-materialization module**
   - **Files:** `app/main.py`, `app/models.py`, `app/tools/laravel.py`, `app/graph.py`, Laravel source-materialization modules.
   - **Problem:** generic response findings and durable canonical records are conflated in a post-run side effect.
   - **Solution to explore:** contain qualification, idempotency, response mapping, and failure visibility behind one materialization module at the Laravel seam.
   - **Benefits:** callers get a small, trustworthy interface: an explanation either has a canonical finding reference or it does not. Tests gain locality for retry and duplicate behavior.

3. **Vendor & Payment Review analysis module**
   - **Files:** vendor/payment graph branches, `vendor_verification_workflow.py`, `duplicate_payment_workflow.py`, `investigation_synthesis.py`, and Laravel tool responses.
   - **Problem:** deterministic signals, static evidence requests, RAG logic, and final wording are distributed across branches with different evidence assumptions.
   - **Solution to explore:** concentrate the selected vertical's source-backed analysis behind a single module after Laravel supplies stable evidence context.
   - **Benefits:** a deeper external seam for frontend/Rex callers; evidence and limitation rules change in one place instead of across graph paths.

4. **Evaluation and capability-gate module**
   - **Files:** tests/fakes, benchmark datasets, quality-gate scripts, relational smoke scripts, and deployment validation.
   - **Problem:** fixture-only benchmark success can conflict with current graph behavior and does not prove live Laravel contract or real-model quality.
   - **Solution to explore:** use one module to combine deterministic unit checks, cross-repository contract tests, real-model sampled evaluation, and capability flags for production claims.
   - **Benefits:** high leverage for release confidence and clearer locality when a route, prompt, or model change regresses the selected vertical.

## Coordination rules

1. Laravel contract changes lead; agent and frontend consumers do not invent absent fields or routes.
2. Agent work is reviewed against the current dirty baseline, but no untracked playbook/prompt asset becomes launch behavior without a source, evaluation, and persistence decision.
3. A workflow may be enabled only when its facts, tool set, degradation behavior, human approval rule, frontend state, and evaluation set agree.
4. Evaluation reports include the exact commit, fixture/data source, model/provider, prompt versions, date, and known limitations.
5. No implementation agent may expand into multi-client portfolio behavior, native client behavior, or autonomous case/package/decision actions under this plan.

