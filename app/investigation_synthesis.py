from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import InvestigationSynthesis


DOMAIN_ORDER = [
    "risk_summary",
    "aggregate_risk_summary",
    "vendor_risk",
    "reconciliation_risk",
    "entity_relationship_risk",
    "alert_recommendations",
    "case_recommendations",
]

SEVERITY_RANK = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

SIGNAL_LABELS = {
    "aggregate_risk": "aggregate risk context",
    "alert_recommendation": "alert recommendation context",
    "case_recommendation": "case recommendation context",
    "duplicate_vendor": "duplicate vendor indicator",
    "entity_overlap": "entity overlap indicator",
    "high_vendor_risk": "high vendor risk",
    "rapid_onboarding": "rapid onboarding or onboarding bypass",
    "reconciliation_mismatch": "reconciliation mismatch",
    "risk_driver": "deterministic risk driver",
    "round_dollar_payments": "round-dollar payment pattern",
    "shared_account": "shared account indicator",
    "threshold_splitting": "threshold splitting indicator",
    "vendor_risk": "vendor risk",
}


@dataclass(frozen=True)
class DomainSignal:
    domain: str
    signal_type: str
    title: str
    severity: str
    score: int | None
    summary: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    anchors: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class CorrelationRule:
    pattern: str
    title: str
    summary: str
    slots: tuple[dict[str, set[str]], ...]
    require_shared_anchor: bool = True
    focus: str = ""


CORRELATION_RULES = [
    CorrelationRule(
        pattern="vendor_entity_overlap",
        title="High vendor risk reinforced by entity overlap",
        summary=(
            "Vendor-risk evidence and entity-relationship evidence point to the same "
            "vendor or related entity."
        ),
        slots=(
            {"domains": {"vendor_risk"}, "types": {"high_vendor_risk", "vendor_risk"}},
            {"domains": {"entity_relationship_risk"}, "types": {"entity_overlap"}},
        ),
        focus="Validate the vendor relationship, ownership, employee overlap, and approval path.",
    ),
    CorrelationRule(
        pattern="reconciliation_threshold_splitting",
        title="Reconciliation mismatch aligns with threshold splitting",
        summary=(
            "A reconciliation mismatch is linked to threshold-splitting evidence on the "
            "same transaction, vendor, or account anchor."
        ),
        slots=(
            {"domains": {"reconciliation_risk", "risk_summary"}, "types": {"reconciliation_mismatch"}},
            {
                "domains": {"risk_summary", "vendor_risk", "aggregate_risk_summary"},
                "types": {"threshold_splitting"},
            },
        ),
        focus="Review the unmatched records, approval threshold, purchase orders, and approver sequence.",
    ),
    CorrelationRule(
        pattern="rapid_onboarding_round_dollar",
        title="Rapid onboarding reinforced by round-dollar payments",
        summary=(
            "Onboarding-control evidence and round-dollar payment evidence share a "
            "vendor, transaction, or entity anchor."
        ),
        slots=(
            {
                "domains": {"vendor_risk", "aggregate_risk_summary", "risk_summary"},
                "types": {"rapid_onboarding"},
            },
            {
                "domains": {"risk_summary", "vendor_risk", "reconciliation_risk", "aggregate_risk_summary"},
                "types": {"round_dollar_payments"},
            },
        ),
        focus="Confirm onboarding timestamps, vendor validation status, invoice support, and payment approvals.",
    ),
    CorrelationRule(
        pattern="duplicate_vendor_shared_account",
        title="Duplicate vendor indicator reinforced by shared account evidence",
        summary=(
            "Duplicate-vendor evidence and shared-account evidence are linked by a "
            "vendor, account, or entity anchor."
        ),
        slots=(
            {
                "domains": {"vendor_risk", "entity_relationship_risk", "risk_summary"},
                "types": {"duplicate_vendor"},
            },
            {
                "domains": {"entity_relationship_risk", "vendor_risk", "risk_summary"},
                "types": {"shared_account"},
            },
        ),
        focus="Compare vendor master records, account ownership, tax documents, and payment routing.",
    ),
]


def synthesize_investigation(
    tool_results: dict[str, Any] | None,
    findings: list[dict[str, Any]] | None = None,
) -> InvestigationSynthesis:
    """Create evidence-linked synthesis from deterministic risk outputs only."""
    resolved_tool_results = tool_results or {}
    resolved_findings = findings or []
    supporting_domains = _source_domains_used(resolved_tool_results)

    signals = _collect_signals(resolved_tool_results, resolved_findings)
    correlated_findings, rejected_correlations = _correlate_signals(signals)
    conflicting_signals = _conflicting_signals(signals, resolved_tool_results, rejected_correlations)
    reinforcing_signals = _reinforcing_signals(signals, correlated_findings, resolved_tool_results)
    priority = _investigation_priority(signals, correlated_findings, conflicting_signals, resolved_tool_results)
    focus = _recommended_focus(correlated_findings, conflicting_signals, signals)
    evidence_summary = _evidence_summary(signals, correlated_findings, conflicting_signals)
    summary = _summary_text(
        correlated_findings=correlated_findings,
        conflicting_signals=conflicting_signals,
        priority=priority,
        focus=focus,
        supporting_domains=supporting_domains,
    )

    return InvestigationSynthesis(
        investigative_summary=summary,
        correlated_findings=correlated_findings,
        reinforcing_signals=reinforcing_signals,
        conflicting_signals=conflicting_signals,
        investigation_priority=priority,
        recommended_investigation_focus=focus,
        supporting_domains=supporting_domains,
        evidence_summary=evidence_summary,
    )


def _collect_signals(tool_results: dict[str, Any], findings: list[dict[str, Any]]) -> list[DomainSignal]:
    signals: list[DomainSignal] = []

    risk_summary = tool_results.get("risk_summary")
    if isinstance(risk_summary, dict):
        signals.extend(_signals_from_risk_summary(risk_summary))

    vendor_risk = tool_results.get("vendor_risk")
    if isinstance(vendor_risk, dict):
        signals.extend(_signals_from_vendor_risk(vendor_risk))

    reconciliation_risk = tool_results.get("reconciliation_risk")
    if isinstance(reconciliation_risk, dict):
        signals.extend(_signals_from_domain_payload("reconciliation_risk", reconciliation_risk))

    entity_relationship_risk = tool_results.get("entity_relationship_risk")
    if isinstance(entity_relationship_risk, dict):
        signals.extend(_signals_from_domain_payload("entity_relationship_risk", entity_relationship_risk))

    aggregate_risk = tool_results.get("aggregate_risk_summary")
    if isinstance(aggregate_risk, dict):
        signals.extend(_signals_from_aggregate_risk(aggregate_risk))
        signals.extend(_signals_from_recommendations("alert_recommendations", aggregate_risk.get("alert_recommendations")))
        signals.extend(_signals_from_recommendations("case_recommendations", aggregate_risk.get("case_recommendations")))

    signals.extend(_signals_from_recommendations("alert_recommendations", tool_results.get("alert_recommendations")))
    signals.extend(_signals_from_recommendations("case_recommendations", tool_results.get("case_recommendations")))

    if not signals:
        signals.extend(_signals_from_findings(findings))

    return _dedupe_signals(signals)


def _signals_from_risk_summary(payload: dict[str, Any]) -> list[DomainSignal]:
    score = _as_int(payload.get("risk_score"))
    default_severity = _severity_from_level(payload.get("risk_level"), score)
    signals: list[DomainSignal] = []

    for driver in payload.get("top_drivers", []):
        if not isinstance(driver, dict):
            continue
        title = str(driver.get("driver") or "Risk pattern worth reviewing")
        summary = str(driver.get("description") or title)
        severity = _normalize_severity(driver.get("severity") or default_severity)
        evidence = _flatten_evidence(driver.get("evidence"), domain="risk_summary", source=title)
        signal_types = _classify_signal_types(
            "risk_summary",
            " ".join([title, summary, _stringify(driver.get("triggered_rules"))]),
            score,
        ) or {"risk_driver"}
        anchors = _anchors_from_evidence(evidence) | _anchors_from_payload(driver)

        for signal_type in signal_types:
            signals.append(
                DomainSignal(
                    domain="risk_summary",
                    signal_type=signal_type,
                    title=title,
                    severity=severity,
                    score=score,
                    summary=summary,
                    evidence=evidence,
                    anchors=anchors,
                )
            )

    return signals


def _signals_from_vendor_risk(payload: dict[str, Any]) -> list[DomainSignal]:
    vendors = payload.get("vendors")
    if isinstance(vendors, list):
        return [
            signal
            for vendor_payload in vendors
            if isinstance(vendor_payload, dict)
            for signal in _signals_from_single_vendor(vendor_payload)
        ]
    return _signals_from_single_vendor(payload)


def _signals_from_single_vendor(payload: dict[str, Any]) -> list[DomainSignal]:
    score = _as_int(payload.get("vendor_risk_score") or payload.get("risk_score"))
    severity = _severity_from_level(payload.get("risk_level"), score)
    title = str(payload.get("vendor_name") or payload.get("name") or "Vendor risk")
    text = " ".join([
        title,
        _stringify(payload.get("triggered_rules")),
        _stringify(payload.get("supporting_evidence")),
        str(payload.get("recommended_next_action") or ""),
    ])
    signal_types = _classify_signal_types("vendor_risk", text, score)
    if score is not None and score >= 70:
        signal_types.add("high_vendor_risk")
    elif score is not None and score >= 40:
        signal_types.add("vendor_risk")

    evidence = _flatten_evidence(
        payload.get("supporting_evidence"),
        payload.get("evidence"),
        payload,
        domain="vendor_risk",
        source=title,
    )
    anchors = _anchors_from_payload(payload) | _anchors_from_evidence(evidence)
    summary = str(
        payload.get("summary")
        or payload.get("description")
        or payload.get("recommended_next_action")
        or f"Vendor risk score is {score}/100."
    )

    return [
        DomainSignal(
            domain="vendor_risk",
            signal_type=signal_type,
            title=title,
            severity=severity,
            score=score,
            summary=summary,
            evidence=evidence,
            anchors=anchors,
        )
        for signal_type in signal_types or {"vendor_risk"}
    ]


def _signals_from_domain_payload(domain: str, payload: dict[str, Any]) -> list[DomainSignal]:
    score_key = {
        "reconciliation_risk": "reconciliation_risk_score",
        "entity_relationship_risk": "entity_relationship_risk_score",
    }.get(domain, "risk_score")
    score = _as_int(payload.get(score_key) or payload.get("risk_score"))
    severity = _severity_from_level(payload.get("risk_level"), score)
    text = " ".join([
        _stringify(payload.get("triggered_rules")),
        _stringify(payload.get("supporting_evidence")),
        _stringify(payload.get("related_entities")),
        _stringify(payload.get("relationships")),
        str(payload.get("recommended_next_action") or ""),
    ])
    signal_types = _classify_signal_types(domain, text, score)
    evidence = _flatten_evidence(
        payload.get("supporting_evidence"),
        payload.get("evidence"),
        payload.get("related_entities"),
        payload.get("relationships"),
        domain=domain,
        source=domain,
    )
    anchors = _anchors_from_payload(payload) | _anchors_from_evidence(evidence)
    summary = str(payload.get("summary") or payload.get("recommended_next_action") or f"{domain} score is {score}/100.")

    return [
        DomainSignal(
            domain=domain,
            signal_type=signal_type,
            title=SIGNAL_LABELS.get(signal_type, signal_type.replace("_", " ")).title(),
            severity=severity,
            score=score,
            summary=summary,
            evidence=evidence,
            anchors=anchors,
        )
        for signal_type in signal_types or {"risk_driver"}
    ]


def _signals_from_aggregate_risk(payload: dict[str, Any]) -> list[DomainSignal]:
    score = _as_int(payload.get("overall_risk_score") or payload.get("risk_score"))
    severity = _severity_from_level(payload.get("overall_risk_level") or payload.get("risk_level"), score)
    evidence = _flatten_evidence(
        payload.get("supporting_evidence"),
        payload.get("top_risk_domains"),
        payload.get("domain_scores"),
        domain="aggregate_risk_summary",
        source="aggregate_risk_summary",
    )
    if score is None and severity in {"info", "low"}:
        return []

    return [
        DomainSignal(
            domain="aggregate_risk_summary",
            signal_type="aggregate_risk",
            title="Aggregate risk summary",
            severity=severity,
            score=score,
            summary=str(payload.get("summary") or f"Aggregate risk level is {severity}."),
            evidence=evidence,
            anchors=_anchors_from_payload(payload) | _anchors_from_evidence(evidence),
        )
    ]


def _signals_from_recommendations(domain: str, payload: Any) -> list[DomainSignal]:
    if not payload:
        return []
    recommendations = payload if isinstance(payload, list) else [payload]
    signal_type = "alert_recommendation" if domain == "alert_recommendations" else "case_recommendation"
    signals: list[DomainSignal] = []

    for i, recommendation in enumerate(recommendations):
        if not isinstance(recommendation, dict):
            continue
        title = str(recommendation.get("title") or recommendation.get("label") or domain.replace("_", " "))
        evidence = _flatten_evidence(
            recommendation.get("supporting_evidence"),
            recommendation.get("evidence"),
            recommendation,
            domain=domain,
            source=title,
        )
        score = _as_int(recommendation.get("risk_score") or recommendation.get("score"))
        severity = _severity_from_level(recommendation.get("severity") or recommendation.get("risk_level"), score)
        signals.append(
            DomainSignal(
                domain=domain,
                signal_type=signal_type,
                title=title,
                severity=severity,
                score=score,
                summary=str(recommendation.get("reason") or recommendation.get("summary") or f"Recommendation {i + 1}."),
                evidence=evidence,
                anchors=_anchors_from_payload(recommendation) | _anchors_from_evidence(evidence),
            )
        )

    return signals


def _signals_from_findings(findings: list[dict[str, Any]]) -> list[DomainSignal]:
    signals: list[DomainSignal] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        title = str(finding.get("title") or "Finding")
        summary = str(finding.get("summary") or "")
        evidence = _flatten_evidence(finding.get("evidence"), domain="risk_summary", source=title)
        signals.append(
            DomainSignal(
                domain="risk_summary",
                signal_type="risk_driver",
                title=title,
                severity=_normalize_severity(finding.get("severity")),
                score=None,
                summary=summary,
                evidence=evidence,
                anchors=_anchors_from_evidence(evidence) | _anchors_from_payload(finding),
            )
        )
    return signals


def _correlate_signals(signals: list[DomainSignal]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    correlated: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for rule in CORRELATION_RULES:
        matches = _match_rule(rule, signals)
        if len(matches) != len(rule.slots) or len({m.domain for m in matches}) < 2:
            continue

        shared_anchors = _shared_anchors(matches)
        evidence = _evidence_for_signals(matches)
        if rule.require_shared_anchor and not shared_anchors:
            rejected.append(
                {
                    "pattern": rule.pattern,
                    "title": rule.title,
                    "domains": _sorted_domains({m.domain for m in matches}),
                    "reason": "No shared vendor, account, transaction, or entity evidence anchor links these signals.",
                    "evidence": evidence,
                }
            )
            continue

        correlated.append(
            {
                "pattern": rule.pattern,
                "title": rule.title,
                "summary": rule.summary,
                "domains": _sorted_domains({m.domain for m in matches}),
                "signals": [m.signal_type for m in matches],
                "shared_evidence_anchors": sorted(shared_anchors)[:8],
                "support_level": "supported",
                "confidence": _confidence(matches),
                "evidence": evidence,
            }
        )

    medium_signals = [
        signal for signal in signals
        if signal.domain != "aggregate_risk_summary" and SEVERITY_RANK.get(signal.severity, 0) >= 2
    ]
    medium_domains = _sorted_domains({signal.domain for signal in medium_signals})
    if len(medium_domains) >= 2 and not correlated:
        selected = _best_signal_per_domain(medium_signals)[:4]
        correlated.append(
            {
                "pattern": "multiple_medium_risk_elevation",
                "title": "Multiple medium-or-higher deterministic risks combine into elevated concern",
                "summary": (
                    "Multiple deterministic domains returned medium-or-higher risk. "
                    "This raises review priority without asserting a single common cause."
                ),
                "domains": _sorted_domains({s.domain for s in selected}),
                "signals": [s.signal_type for s in selected],
                "shared_evidence_anchors": [],
                "support_level": "aggregate",
                "confidence": _confidence(selected),
                "evidence": _evidence_for_signals(selected),
            }
        )

    return _dedupe_correlated_findings(correlated), rejected


def _match_rule(rule: CorrelationRule, signals: list[DomainSignal]) -> list[DomainSignal]:
    candidates_by_slot = [
        sorted(
            [
                signal
                for signal in signals
                if signal.domain in slot["domains"] and signal.signal_type in slot["types"]
            ],
            key=_signal_sort_key,
            reverse=True,
        )
        for slot in rule.slots
    ]
    if any(not candidates for candidates in candidates_by_slot):
        return []

    def _search(slot_index: int, used_domains: set[str], selected: list[DomainSignal]) -> list[DomainSignal] | None:
        if slot_index == len(candidates_by_slot):
            return selected

        for signal in candidates_by_slot[slot_index]:
            if signal.domain in used_domains:
                continue
            result = _search(
                slot_index + 1,
                used_domains | {signal.domain},
                [*selected, signal],
            )
            if result is not None:
                return result
        return None

    return _search(0, set(), []) or []


def _conflicting_signals(
    signals: list[DomainSignal],
    tool_results: dict[str, Any],
    rejected_correlations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []

    for rejected in rejected_correlations:
        conflicts.append(
            {
                "type": "unsupported_correlation_suppressed",
                "summary": (
                    f"{rejected['title']} was not produced because {rejected['reason']}"
                ),
                "domains": rejected["domains"],
                "evidence": rejected["evidence"],
            }
        )

    vendor_high = [
        signal for signal in signals
        if signal.domain == "vendor_risk" and signal.signal_type == "high_vendor_risk"
    ]
    entity_payload = tool_results.get("entity_relationship_risk")
    if vendor_high and isinstance(entity_payload, dict):
        entity_score = _as_int(entity_payload.get("entity_relationship_risk_score") or entity_payload.get("risk_score"))
        entity_signals = [
            signal for signal in signals
            if signal.domain == "entity_relationship_risk" and signal.signal_type == "entity_overlap"
        ]
        if (entity_score is None or entity_score < 40) and not entity_signals:
            conflicts.append(
                {
                    "type": "vendor_risk_not_reinforced_by_entity_graph",
                    "summary": (
                        "Vendor risk is elevated, but the entity-relationship output did not return "
                        "a supporting overlap signal."
                    ),
                    "domains": ["vendor_risk", "entity_relationship_risk"],
                    "evidence": _evidence_for_signals(vendor_high[:1]),
                }
            )

    aggregate_payload = tool_results.get("aggregate_risk_summary")
    if isinstance(aggregate_payload, dict):
        aggregate_score = _as_int(aggregate_payload.get("overall_risk_score") or aggregate_payload.get("risk_score"))
        high_domain_signals = [
            signal for signal in signals
            if signal.domain != "aggregate_risk_summary" and SEVERITY_RANK.get(signal.severity, 0) >= 3
        ]
        if aggregate_score is not None and aggregate_score < 40 and high_domain_signals:
            conflicts.append(
                {
                    "type": "aggregate_risk_below_domain_signal",
                    "summary": "Aggregate risk is low while at least one domain-specific deterministic signal is high.",
                    "domains": _sorted_domains({"aggregate_risk_summary", *(s.domain for s in high_domain_signals)}),
                    "evidence": _evidence_for_signals(high_domain_signals[:3]),
                }
            )

    return _dedupe_conflicts(conflicts)


def _reinforcing_signals(
    signals: list[DomainSignal],
    correlated_findings: list[dict[str, Any]],
    tool_results: dict[str, Any],
) -> list[dict[str, Any]]:
    correlated_domains = {
        domain
        for finding in correlated_findings
        for domain in finding.get("domains", [])
    }
    reinforcing: list[dict[str, Any]] = [
        {
            "signal": signal.signal_type,
            "label": SIGNAL_LABELS.get(signal.signal_type, signal.signal_type.replace("_", " ")),
            "domain": signal.domain,
            "severity": signal.severity,
            "summary": signal.summary,
            "evidence": _limit_evidence(signal.evidence, 3),
        }
        for signal in signals
        if signal.domain in correlated_domains and signal.signal_type != "aggregate_risk"
    ]

    aggregate_payload = tool_results.get("aggregate_risk_summary")
    if isinstance(aggregate_payload, dict) and correlated_findings:
        score = _as_int(aggregate_payload.get("overall_risk_score") or aggregate_payload.get("risk_score"))
        level = _severity_from_level(aggregate_payload.get("overall_risk_level") or aggregate_payload.get("risk_level"), score)
        if SEVERITY_RANK.get(level, 0) >= 2:
            reinforcing.append(
                {
                    "signal": "aggregate_risk",
                    "label": "aggregate risk context",
                    "domain": "aggregate_risk_summary",
                    "severity": level,
                    "summary": str(aggregate_payload.get("summary") or f"Aggregate risk is {level}."),
                    "evidence": _limit_evidence(
                        _flatten_evidence(
                            aggregate_payload.get("supporting_evidence"),
                            domain="aggregate_risk_summary",
                            source="aggregate_risk_summary",
                        ),
                        3,
                    ),
                }
            )

    return _dedupe_reinforcing(reinforcing)


def _investigation_priority(
    signals: list[DomainSignal],
    correlated_findings: list[dict[str, Any]],
    conflicting_signals: list[dict[str, Any]],
    tool_results: dict[str, Any],
) -> str:
    highest_severity = max((SEVERITY_RANK.get(signal.severity, 0) for signal in signals), default=0)
    highest_score = max((_as_int(signal.score) or 0 for signal in signals), default=0)
    aggregate_payload = tool_results.get("aggregate_risk_summary")
    if isinstance(aggregate_payload, dict):
        highest_score = max(highest_score, _as_int(aggregate_payload.get("overall_risk_score")) or 0)

    strong_correlations = [
        finding for finding in correlated_findings
        if finding.get("pattern") != "multiple_medium_risk_elevation"
    ]

    if highest_severity >= 4 or highest_score >= 90:
        return "critical"
    if strong_correlations:
        return "high"
    if correlated_findings and len(correlated_findings[0].get("domains", [])) >= 3:
        return "high"
    if highest_severity >= 3 or highest_score >= 70:
        return "high"
    if correlated_findings or conflicting_signals or highest_severity >= 2 or highest_score >= 40:
        return "medium"
    return "low"


def _recommended_focus(
    correlated_findings: list[dict[str, Any]],
    conflicting_signals: list[dict[str, Any]],
    signals: list[DomainSignal],
) -> list[str]:
    focus: list[str] = []
    focus_by_pattern = {rule.pattern: rule.focus for rule in CORRELATION_RULES}
    focus_by_pattern["multiple_medium_risk_elevation"] = (
        "Review the medium-or-higher domains together, but keep their evidence chains separate."
    )

    for finding in correlated_findings:
        pattern = finding.get("pattern")
        if pattern in focus_by_pattern:
            focus.append(focus_by_pattern[pattern])

    if conflicting_signals:
        focus.append("Resolve conflicting or unsupported signals before treating separate domain findings as related.")

    if not focus and signals:
        top_signal = sorted(signals, key=_signal_sort_key, reverse=True)[0]
        focus.append(f"Review the strongest deterministic signal: {top_signal.title}.")

    if not focus:
        focus.append("Monitor deterministic risk outputs; no cross-domain investigation focus is supported.")

    return _dedupe_strings(focus)[:5]


def _evidence_summary(
    signals: list[DomainSignal],
    correlated_findings: list[dict[str, Any]],
    conflicting_signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for finding in correlated_findings:
        evidence.extend(finding.get("evidence", []))
    for conflict in conflicting_signals:
        evidence.extend(conflict.get("evidence", []))
    if not evidence:
        for signal in sorted(signals, key=_signal_sort_key, reverse=True)[:5]:
            evidence.extend(signal.evidence)
    return _unique_evidence(evidence)[:30]


def _summary_text(
    *,
    correlated_findings: list[dict[str, Any]],
    conflicting_signals: list[dict[str, Any]],
    priority: str,
    focus: list[str],
    supporting_domains: list[str],
) -> str:
    domain_text = ", ".join(supporting_domains) if supporting_domains else "no risk domains"
    focus_text = focus[0] if focus else "No focused investigation is supported."

    if correlated_findings:
        return (
            f"Deterministic risk services produced {len(correlated_findings)} supported "
            f"cross-domain synthesis finding(s) across {domain_text}. Investigation priority is {priority}. "
            f"Primary focus: {focus_text} This synthesis is evidence-linked and does not create alerts or cases."
        )

    if conflicting_signals:
        return (
            f"Deterministic risk services returned signals across {domain_text}, but supported cross-domain "
            f"correlation is limited by conflicts or missing shared evidence. Investigation priority is {priority}. "
            f"Primary focus: {focus_text} No alerts or cases were created."
        )

    return (
        f"No supported cross-domain investigation pattern was identified across {domain_text}. "
        f"Investigation priority is {priority}. No alerts or cases were created."
    )


def _source_domains_used(tool_results: dict[str, Any]) -> list[str]:
    domains: set[str] = set()
    for domain in DOMAIN_ORDER:
        payload = tool_results.get(domain)
        if payload:
            domains.add(domain)
    aggregate = tool_results.get("aggregate_risk_summary")
    if isinstance(aggregate, dict):
        if aggregate.get("alert_recommendations"):
            domains.add("alert_recommendations")
        if aggregate.get("case_recommendations"):
            domains.add("case_recommendations")
    return _sorted_domains(domains)


def _classify_signal_types(domain: str, text: str, score: int | None) -> set[str]:
    normalized = text.lower().replace("-", " ")
    signal_types: set[str] = set()

    if domain == "vendor_risk":
        if score is not None and score >= 70:
            signal_types.add("high_vendor_risk")
        elif score is not None and score >= 40:
            signal_types.add("vendor_risk")

    if "employee vendor" in normalized or "entity overlap" in normalized or "overlap" in normalized or "same tax" in normalized:
        signal_types.add("entity_overlap")
    if "reconciliation" in normalized and (
        "mismatch" in normalized or "discrepancy" in normalized or "unmatched" in normalized
    ):
        signal_types.add("reconciliation_mismatch")
    if "threshold" in normalized and ("split" in normalized or "just below" in normalized or "approval" in normalized):
        signal_types.add("threshold_splitting")
    if "rapid onboarding" in normalized or "new vendor" in normalized or "recently onboard" in normalized:
        signal_types.add("rapid_onboarding")
    if "before onboarding" in normalized or "onboarding bypass" in normalized or "onboarding incomplete" in normalized:
        signal_types.add("rapid_onboarding")
    if "round dollar" in normalized or "round amount" in normalized or "exact round" in normalized:
        signal_types.add("round_dollar_payments")
    if "duplicate vendor" in normalized or "name variation" in normalized or "duplicate name" in normalized:
        signal_types.add("duplicate_vendor")
    if "shared bank" in normalized or "same bank" in normalized or "shared account" in normalized or "same account" in normalized:
        signal_types.add("shared_account")

    return signal_types


def _flatten_evidence(*values: Any, domain: str, source: str) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for value in values:
        evidence.extend(_flatten_evidence_value(value, domain=domain, source=source))
    return _unique_evidence(evidence)


def _flatten_evidence_value(value: Any, *, domain: str, source: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [
            item
            for entry in value
            for item in _flatten_evidence_value(entry, domain=domain, source=source)
        ]
    if not isinstance(value, dict):
        return []

    if _looks_like_evidence(value):
        return [_normalize_evidence_item(value, domain=domain, source=source)]

    evidence: list[dict[str, Any]] = []
    for key in (
        "evidence",
        "supporting_evidence",
        "transactions",
        "vendors",
        "related_entities",
        "relationships",
        "mismatches",
        "domain_scores",
    ):
        if key in value:
            evidence.extend(_flatten_evidence_value(value.get(key), domain=domain, source=source))
    return evidence


def _looks_like_evidence(value: dict[str, Any]) -> bool:
    return any(
        key in value
        for key in (
            "type",
            "id",
            "vendor_id",
            "transaction_id",
            "entity_id",
            "bank_account_id",
            "employee_id",
            "account_id",
            "rule",
        )
    )


def _normalize_evidence_item(item: dict[str, Any], *, domain: str, source: str) -> dict[str, Any]:
    allowed_keys = {
        "type",
        "id",
        "label",
        "description",
        "vendor_id",
        "vendor_name",
        "transaction_id",
        "entity_id",
        "bank_account_id",
        "employee_id",
        "account_id",
        "rule",
        "amount",
        "amount_usd",
        "date",
        "score",
        "risk_level",
    }
    normalized = {
        key: value
        for key, value in item.items()
        if key in allowed_keys and value is not None and _is_scalar(value)
    }
    normalized.setdefault("type", "deterministic_evidence")
    normalized["domain"] = domain
    normalized["source"] = source
    return normalized


def _anchors_from_evidence(evidence: list[dict[str, Any]]) -> set[str]:
    anchors: set[str] = set()
    for item in evidence:
        for key in (
            "id",
            "vendor_id",
            "vendor_name",
            "transaction_id",
            "entity_id",
            "bank_account_id",
            "employee_id",
            "account_id",
        ):
            if item.get(key):
                anchors.add(_anchor(item[key]))
    return anchors


def _anchors_from_payload(payload: dict[str, Any]) -> set[str]:
    anchors: set[str] = set()
    for key in (
        "id",
        "vendor_id",
        "vendor_name",
        "name",
        "transaction_id",
        "entity_id",
        "bank_account_id",
        "employee_id",
        "account_id",
    ):
        value = payload.get(key)
        if value:
            anchors.add(_anchor(value))
    return anchors


def _shared_anchors(signals: list[DomainSignal]) -> set[str]:
    anchor_sets = [signal.anchors for signal in signals if signal.anchors]
    if len(anchor_sets) < len(signals):
        return set()
    shared = set(anchor_sets[0])
    for anchors in anchor_sets[1:]:
        shared &= anchors
    return shared


def _evidence_for_signals(signals: list[DomainSignal]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for signal in signals:
        evidence.extend(signal.evidence)
    return _unique_evidence(evidence)[:20]


def _unique_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for item in evidence:
        key = (
            str(item.get("domain", "")),
            str(item.get("type", "")),
            str(item.get("id") or item.get("transaction_id") or item.get("vendor_id") or item.get("entity_id") or ""),
            str(item.get("source", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _limit_evidence(evidence: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return _unique_evidence(evidence)[:limit]


def _best_signal_per_domain(signals: list[DomainSignal]) -> list[DomainSignal]:
    by_domain: dict[str, DomainSignal] = {}
    for signal in sorted(signals, key=_signal_sort_key, reverse=True):
        by_domain.setdefault(signal.domain, signal)
    return [by_domain[domain] for domain in _sorted_domains(set(by_domain))]


def _dedupe_signals(signals: list[DomainSignal]) -> list[DomainSignal]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[DomainSignal] = []
    for signal in signals:
        key = (signal.domain, signal.signal_type, signal.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(signal)
    return unique


def _dedupe_correlated_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for finding in findings:
        pattern = str(finding.get("pattern"))
        if pattern in seen:
            continue
        seen.add(pattern)
        unique.append(finding)
    return unique


def _dedupe_conflicts(conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for conflict in conflicts:
        key = (str(conflict.get("type")), str(conflict.get("summary")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(conflict)
    return unique


def _dedupe_reinforcing(reinforcing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for item in reinforcing:
        key = (str(item.get("domain")), str(item.get("signal")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _signal_sort_key(signal: DomainSignal) -> tuple[int, int, int, int]:
    score = signal.score if signal.score is not None else 0
    has_evidence = 1 if signal.evidence else 0
    domain_rank = len(DOMAIN_ORDER) - DOMAIN_ORDER.index(signal.domain) if signal.domain in DOMAIN_ORDER else 0
    return (SEVERITY_RANK.get(signal.severity, 0), score, has_evidence, domain_rank)


def _confidence(signals: list[DomainSignal]) -> float:
    if not signals:
        return 0.0
    severity_component = max(SEVERITY_RANK.get(signal.severity, 0) for signal in signals) / 4
    evidence_component = min(1.0, sum(1 for signal in signals if signal.evidence) / len(signals))
    anchor_component = 1.0 if _shared_anchors(signals) else 0.75
    return round(min(0.95, 0.35 + (0.3 * severity_component) + (0.2 * evidence_component) + (0.1 * anchor_component)), 2)


def _sorted_domains(domains: set[str]) -> list[str]:
    return sorted(domains, key=lambda domain: DOMAIN_ORDER.index(domain) if domain in DOMAIN_ORDER else len(DOMAIN_ORDER))


def _normalize_severity(value: Any) -> str:
    if value is None:
        return "info"
    normalized = str(value).lower()
    mapping = {
        "warning": "medium",
        "moderate": "medium",
    }
    normalized = mapping.get(normalized, normalized)
    return normalized if normalized in SEVERITY_RANK else "info"


def _severity_from_level(level: Any, score: int | None) -> str:
    severity = _normalize_severity(level)
    if severity != "info":
        return severity
    if score is None:
        return "info"
    if score >= 90:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    if score > 0:
        return "low"
    return "info"


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _anchor(value: Any) -> str:
    return str(value).strip().lower()


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_stringify(item) for item in value)
    if isinstance(value, dict):
        return " ".join(f"{key} {_stringify(item)}" for key, item in value.items())
    return str(value)


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))
