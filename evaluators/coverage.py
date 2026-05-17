"""Benchmark coverage matrix computation for Brevix AI fraud scenarios."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


# Tags every mature benchmark suite should exercise.
RECOMMENDED_TAGS: list[str] = [
    "after_hours",
    "duplicate",
    "entity_graph",
    "false_positive_guardrail",
    "onboarding",
    "payments",
    "payroll",
    "reconciliation",
    "threshold",
    "vendor",
]

# Severity levels the suite should represent.
STANDARD_SEVERITIES: list[str] = ["critical", "high", "medium", "low"]


@dataclass
class CoverageMatrix:
    generated_at: str
    total_scenarios: int
    by_category: dict[str, int]
    by_risk_type: dict[str, int]
    by_severity: dict[str, int]
    by_tag: dict[str, int]
    missing_recommended_tags: list[str]
    duplicate_scenario_ids: list[str]
    missing_evidence_patterns: list[str]
    missing_false_positive_guardrails: list[str]
    recommended_gaps: list[str] = field(default_factory=list)


def compute_coverage(dataset: list[dict[str, Any]]) -> CoverageMatrix:
    """Compute a CoverageMatrix from a validated benchmark dataset."""
    by_category: dict[str, int] = {}
    by_risk_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_tag: dict[str, int] = {}
    seen_ids: dict[str, int] = {}
    missing_evidence: list[str] = []
    missing_guardrails: list[str] = []

    for scenario in dataset:
        sid = scenario.get("id", "")

        # ID deduplication
        seen_ids[sid] = seen_ids.get(sid, 0) + 1

        # Category counts
        cat = scenario.get("category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1

        # Risk type counts
        rt = scenario.get("risk_type", "unknown")
        by_risk_type[rt] = by_risk_type.get(rt, 0) + 1

        # Severity counts
        sev = scenario.get("expected_severity", "unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1

        # Tag counts
        for tag in scenario.get("tags", []):
            by_tag[tag] = by_tag.get(tag, 0) + 1

        # Data quality: expected_evidence_patterns
        if not scenario.get("expected_evidence_patterns"):
            missing_evidence.append(sid)

        # Data quality: false_positive_guardrails
        if not scenario.get("false_positive_guardrails"):
            missing_guardrails.append(sid)

    duplicate_ids = sorted(sid for sid, count in seen_ids.items() if count > 1)
    missing_tags = [t for t in RECOMMENDED_TAGS if by_tag.get(t, 0) == 0]

    gaps = _build_gaps(
        by_category=by_category,
        by_severity=by_severity,
        missing_tags=missing_tags,
        duplicate_ids=duplicate_ids,
        missing_evidence=missing_evidence,
        missing_guardrails=missing_guardrails,
    )

    return CoverageMatrix(
        generated_at=_now(),
        total_scenarios=len(dataset),
        by_category=dict(sorted(by_category.items())),
        by_risk_type=dict(sorted(by_risk_type.items())),
        by_severity=dict(sorted(by_severity.items())),
        by_tag=dict(sorted(by_tag.items())),
        missing_recommended_tags=missing_tags,
        duplicate_scenario_ids=duplicate_ids,
        missing_evidence_patterns=missing_evidence,
        missing_false_positive_guardrails=missing_guardrails,
        recommended_gaps=gaps,
    )


def coverage_to_json(matrix: CoverageMatrix) -> str:
    return json.dumps(asdict(matrix), indent=2)


def coverage_to_markdown(matrix: CoverageMatrix) -> str:
    lines: list[str] = []

    lines += [
        "# Brevix AI Benchmark Coverage Matrix",
        "",
        f"Generated: {matrix.generated_at}",
        "",
    ]

    # Summary
    lines += [
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total scenarios | {matrix.total_scenarios} |",
        f"| Categories | {len(matrix.by_category)} |",
        f"| Risk types | {len(matrix.by_risk_type)} |",
        f"| Severity levels | {len(matrix.by_severity)} |",
        f"| Unique tags | {len(matrix.by_tag)} |",
        "",
    ]

    # Category coverage
    lines += _count_table("Category Coverage", "Category", matrix.by_category)

    # Risk type coverage
    lines += _count_table("Risk Type Coverage", "Risk Type", matrix.by_risk_type)

    # Severity coverage
    lines += _count_table("Severity Coverage", "Severity", matrix.by_severity)

    # Tag coverage
    lines += _count_table("Tag Coverage", "Tag", matrix.by_tag)

    # Data quality checks
    lines += [
        "## Data Quality Checks",
        "",
        "| Check | Status | Detail |",
        "|-------|--------|--------|",
    ]
    lines += _quality_row(
        "Duplicate scenario IDs",
        matrix.duplicate_scenario_ids,
        "None found",
    )
    lines += _quality_row(
        "Missing evidence patterns",
        matrix.missing_evidence_patterns,
        "None found",
    )
    lines += _quality_row(
        "Missing false-positive guardrails",
        matrix.missing_false_positive_guardrails,
        "None found",
    )
    lines += _quality_row(
        "Missing recommended tags",
        matrix.missing_recommended_tags,
        "All recommended tags covered",
    )
    lines.append("")

    # Recommended gaps
    lines += ["## Recommended Gaps to Fill Next", ""]
    if matrix.recommended_gaps:
        for gap in matrix.recommended_gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("No gaps identified. Coverage looks complete.")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count_table(heading: str, col_label: str, counts: dict[str, int]) -> list[str]:
    sorted_rows = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    lines = [
        f"## {heading}",
        "",
        f"| {col_label} | Scenarios |",
        f"|{'-' * (len(col_label) + 2)}|-----------|",
    ]
    for name, count in sorted_rows:
        lines.append(f"| {name} | {count} |")
    lines.append("")
    return lines


def _quality_row(label: str, issues: list[str], ok_text: str) -> list[str]:
    if not issues:
        return [f"| {label} | PASS | {ok_text} |"]
    detail = ", ".join(f"`{i}`" for i in issues[:5])
    if len(issues) > 5:
        detail += f" (+{len(issues) - 5} more)"
    return [f"| {label} | FAIL | {detail} |"]


def _build_gaps(
    *,
    by_category: dict[str, int],
    by_severity: dict[str, int],
    missing_tags: list[str],
    duplicate_ids: list[str],
    missing_evidence: list[str],
    missing_guardrails: list[str],
) -> list[str]:
    gaps: list[str] = []

    for tag in missing_tags:
        gaps.append(
            f"Tag `{tag}` has 0 scenarios — add at least one scenario that exercises this pattern."
        )

    for sev in STANDARD_SEVERITIES:
        if by_severity.get(sev, 0) == 0:
            gaps.append(
                f"Severity `{sev}` has no coverage — consider adding a scenario at this severity level."
            )

    thin_categories = [cat for cat, n in by_category.items() if n == 1]
    for cat in sorted(thin_categories):
        gaps.append(
            f"Category `{cat}` has only 1 scenario — thin coverage increases regression risk."
        )

    if duplicate_ids:
        gaps.append(
            f"Duplicate scenario IDs detected: {', '.join(duplicate_ids)}. Remove or rename duplicates."
        )

    if missing_evidence:
        gaps.append(
            f"{len(missing_evidence)} scenario(s) have no expected_evidence_patterns: "
            f"{', '.join(missing_evidence[:3])}{'...' if len(missing_evidence) > 3 else ''}. "
            "Add patterns to enable evidence completeness evaluation."
        )

    if missing_guardrails:
        gaps.append(
            f"{len(missing_guardrails)} scenario(s) have no false_positive_guardrails: "
            f"{', '.join(missing_guardrails[:3])}{'...' if len(missing_guardrails) > 3 else ''}. "
            "Add guardrails to prevent false-positive accumulation."
        )

    return gaps
