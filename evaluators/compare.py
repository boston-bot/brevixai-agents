"""Pure comparison logic for Brevix benchmark reports.

No I/O — all functions accept and return plain data so they are easy to test.
The CLI in scripts/compare_benchmark_reports.py handles file loading and output.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from evaluators.report import BenchmarkReport

# Which direction means "better" for each metric.
_HIGHER_IS_BETTER = frozenset({
    "pass_rate",
    "severity_accuracy",
    "evidence_completeness_avg",
    "false_positive_pass_rate",
})
_LOWER_IS_BETTER = frozenset({
    "hallucination_failure_count",
    "average_latency_ms",
})

_UNCHANGED_EPSILON = 1e-6


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MetricDelta:
    metric: str
    base: float
    current: float
    delta: float        # current - base
    direction: str      # "improved" | "degraded" | "unchanged"


@dataclass
class PromptChange:
    prompt_name: str
    base_version: str
    current_version: str
    base_hash: str
    current_hash: str
    changed: bool


@dataclass
class ReportComparison:
    base_generated_at: str
    current_generated_at: str
    metric_deltas: list[MetricDelta]
    newly_failed: list[str]
    newly_passing: list[str]
    prompt_changes: list[PromptChange]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compare_reports(base: BenchmarkReport, current: BenchmarkReport) -> ReportComparison:
    """Diff two benchmark reports and return a structured comparison."""
    return ReportComparison(
        base_generated_at=base.generated_at,
        current_generated_at=current.generated_at,
        metric_deltas=_compare_metrics(base, current),
        newly_failed=_newly_failed(base, current),
        newly_passing=_newly_passing(base, current),
        prompt_changes=_compare_prompts(base.prompts_used, current.prompts_used),
    )


def comparison_to_json(comparison: ReportComparison) -> str:
    return json.dumps(asdict(comparison), indent=2)


def comparison_to_markdown(comparison: ReportComparison) -> str:
    lines: list[str] = [
        "# Brevix AI Benchmark Comparison",
        "",
        f"- **Base:** {comparison.base_generated_at}",
        f"- **Current:** {comparison.current_generated_at}",
        "",
        "> Informational only — this comparison does not affect CI pass/fail.",
        "",
        "## Metric Deltas",
        "",
        "| Metric | Base | Current | Delta | Direction |",
        "|--------|------|---------|-------|-----------|",
    ]
    for d in comparison.metric_deltas:
        sign = "+" if d.delta >= 0 else ""
        direction_label = {"improved": "Better", "degraded": "Worse", "unchanged": "Same"}[d.direction]
        lines.append(
            f"| {d.metric} | {_fmt(d.base)} | {_fmt(d.current)}"
            f" | {sign}{_fmt(d.delta)} | {direction_label} |"
        )
    lines.append("")

    lines += ["## Scenario Changes", ""]
    newly_failed_str = (
        ", ".join(f"`{s}`" for s in comparison.newly_failed)
        if comparison.newly_failed else "—"
    )
    newly_passing_str = (
        ", ".join(f"`{s}`" for s in comparison.newly_passing)
        if comparison.newly_passing else "—"
    )
    lines.append(f"**Newly failed ({len(comparison.newly_failed)}):** {newly_failed_str}")
    lines.append("")
    lines.append(f"**Newly passing ({len(comparison.newly_passing)}):** {newly_passing_str}")
    lines.append("")

    if comparison.prompt_changes:
        lines += [
            "## Prompt Changes",
            "",
            "| Prompt | Base Hash | Current Hash | Changed |",
            "|--------|-----------|--------------|---------|",
        ]
        for p in comparison.prompt_changes:
            base_short = p.base_hash[:8] if p.base_hash else "—"
            curr_short = p.current_hash[:8] if p.current_hash else "—"
            changed_str = "YES" if p.changed else "—"
            lines.append(
                f"| {p.prompt_name} | `{base_short}` | `{curr_short}` | {changed_str} |"
            )
        lines.append("")

    return "\n".join(lines)


def print_comparison(comparison: ReportComparison) -> None:
    bar = "=" * 62
    thin = "-" * 58

    print(f"\n{bar}")
    print("Brevix AI Benchmark Comparison")
    print(bar)
    print(f"\n  Base:    {comparison.base_generated_at}")
    print(f"  Current: {comparison.current_generated_at}\n")

    print(f"  Metric Deltas\n  {thin}")
    for d in comparison.metric_deltas:
        _print_delta(d)
    print()

    print(f"  Scenario Changes\n  {thin}")
    failed_str = ", ".join(comparison.newly_failed) if comparison.newly_failed else "—"
    passing_str = ", ".join(comparison.newly_passing) if comparison.newly_passing else "—"
    print(f"  Newly failed  ({len(comparison.newly_failed)}): {failed_str}")
    print(f"  Newly passing ({len(comparison.newly_passing)}): {passing_str}")

    if comparison.prompt_changes:
        print(f"\n  Prompt Changes\n  {thin}")
        for p in comparison.prompt_changes:
            if p.changed:
                base_short = p.base_hash[:8] if p.base_hash else "—"
                curr_short = p.current_hash[:8] if p.current_hash else "—"
                print(f"  CHANGED  {p.prompt_name:<30} {base_short} -> {curr_short}")
            else:
                short = p.current_hash[:8] if p.current_hash else "—"
                print(f"  SAME     {p.prompt_name:<30} {short}")

    improved = sum(1 for d in comparison.metric_deltas if d.direction == "improved")
    degraded = sum(1 for d in comparison.metric_deltas if d.direction == "degraded")
    prompt_changes = sum(1 for p in comparison.prompt_changes if p.changed)

    print(f"\n{bar}")
    print(
        f"Summary: {improved} improved, {degraded} degraded"
        f" | {len(comparison.newly_failed)} new failure(s),"
        f" {len(comparison.newly_passing)} new pass(es)"
        f" | {prompt_changes} prompt change(s)"
    )
    print("(Informational only — does not affect CI pass/fail)")
    print(f"{bar}\n")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compare_metrics(base: BenchmarkReport, current: BenchmarkReport) -> list[MetricDelta]:
    pairs: list[tuple[str, float, float]] = [
        ("pass_rate",                    base.pass_rate,                    current.pass_rate),
        ("severity_accuracy",            base.severity_accuracy,            current.severity_accuracy),
        ("evidence_completeness_avg",    base.evidence_completeness_avg,    current.evidence_completeness_avg),
        ("false_positive_pass_rate",     base.false_positive_pass_rate,     current.false_positive_pass_rate),
        ("hallucination_failure_count",  float(base.hallucination_failure_count),  float(current.hallucination_failure_count)),
        ("average_latency_ms",           base.average_latency_ms,           current.average_latency_ms),
    ]
    return [_make_delta(metric, b, c) for metric, b, c in pairs]


def _make_delta(metric: str, base_val: float, current_val: float) -> MetricDelta:
    delta = round(current_val - base_val, 6)
    return MetricDelta(
        metric=metric,
        base=base_val,
        current=current_val,
        delta=delta,
        direction=_direction(metric, delta),
    )


def _direction(metric: str, delta: float) -> str:
    if abs(delta) < _UNCHANGED_EPSILON:
        return "unchanged"
    if metric in _HIGHER_IS_BETTER:
        return "improved" if delta > 0 else "degraded"
    return "improved" if delta < 0 else "degraded"


def _newly_failed(base: BenchmarkReport, current: BenchmarkReport) -> list[str]:
    return sorted(set(current.failed_scenario_ids) - set(base.failed_scenario_ids))


def _newly_passing(base: BenchmarkReport, current: BenchmarkReport) -> list[str]:
    return sorted(set(base.failed_scenario_ids) - set(current.failed_scenario_ids))


def _compare_prompts(
    base_prompts: list[dict[str, str]],
    current_prompts: list[dict[str, str]],
) -> list[PromptChange]:
    base_by_name = {p["prompt_name"]: p for p in base_prompts}
    curr_by_name = {p["prompt_name"]: p for p in current_prompts}
    all_names = sorted(set(base_by_name) | set(curr_by_name))

    changes: list[PromptChange] = []
    for name in all_names:
        b = base_by_name.get(name, {})
        c = curr_by_name.get(name, {})
        base_hash = b.get("prompt_hash", "")
        curr_hash = c.get("prompt_hash", "")
        changes.append(PromptChange(
            prompt_name=name,
            base_version=b.get("prompt_version", ""),
            current_version=c.get("prompt_version", ""),
            base_hash=base_hash,
            current_hash=curr_hash,
            changed=base_hash != curr_hash,
        ))
    return changes


def _print_delta(d: MetricDelta) -> None:
    labels = {"improved": "BETTER ", "degraded": "WORSE  ", "unchanged": "SAME   "}
    label = labels[d.direction]
    if d.direction == "unchanged":
        print(f"  {label}  {d.metric:<34} {_fmt(d.current)}  (no change)")
    else:
        sign = "+" if d.delta >= 0 else ""
        print(
            f"  {label}  {d.metric:<34}"
            f" {_fmt(d.base)} -> {_fmt(d.current)}  ({sign}{_fmt(d.delta)})"
        )


def _fmt(value: float) -> str:
    """Format a metric value, stripping unnecessary trailing zeros."""
    if value == int(value) and abs(value) < 10_000:
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")
