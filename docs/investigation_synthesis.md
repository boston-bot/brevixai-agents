# Investigation Synthesis

Phase 4 adds an investigation synthesis layer to the LangGraph workflow. The layer is a reviewer-facing reasoning component, not a scoring engine and not an action engine.

## Philosophy

Synthesis starts after deterministic risk services have already returned their outputs. It consumes:

- aggregate risk summary
- vendor risk
- reconciliation risk
- entity relationship risk
- alert recommendation context
- case recommendation context
- risk-summary findings already produced by deterministic tools

The layer looks for relationships across these domains, such as vendor risk reinforced by entity overlap or reconciliation mismatch reinforced by threshold-splitting evidence. It can raise investigation priority when several medium deterministic signals appear together, but it cannot invent new scores or override the source service scores.

## Evidence-Linked Reasoning

Every correlated finding must be tied to deterministic evidence returned by the source domains. A correlation is supported only when the participating signals have compatible evidence anchors such as a shared vendor ID, transaction ID, account ID, employee ID, or entity relationship ID.

If two domains are elevated but do not share an evidence anchor, synthesis suppresses the direct correlation and records a conflicting signal instead. This keeps the output useful for investigators without implying unsupported relationships.

## Scoring vs Synthesis

Deterministic scoring services answer: "How risky is this domain according to fixed rules?"

Investigation synthesis answers: "How should a human investigator organize the already-scored findings across domains?"

The synthesis layer does not:

- compute authoritative risk scores
- change vendor, reconciliation, entity, alert, or case scores
- replace deterministic threshold logic
- query the database directly
- retrieve extra evidence outside the approved Laravel tool outputs

## No Autonomous Actions

Synthesis output is advisory. It can recommend investigation focus, but it cannot create alerts, create cases, suppress alerts, resolve alerts, send reports, or mutate records.

Action handling remains downstream in the existing action gate. The graph still returns review-oriented recommendations only, and sensitive action types remain approval-gated.

## Output Contract

The API response includes `investigative_synthesis` with:

- `investigative_summary`
- `correlated_findings`
- `reinforcing_signals`
- `conflicting_signals`
- `investigation_priority`: `low`, `medium`, `high`, or `critical`
- `recommended_investigation_focus`
- `supporting_domains`
- `evidence_summary`

## Observability

The `investigation_synthesis` graph step records:

- source domains used
- prompt name, version, and hash from `app/prompts/investigation_synthesis.v1.md`
- synthesis latency
- provider name and model name
- token fields, currently zero for deterministic synthesis

This makes synthesis behavior traceable without introducing external calls or autonomous actions.
