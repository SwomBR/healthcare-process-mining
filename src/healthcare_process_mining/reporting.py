"""Build a plain-language Markdown report from computed results.

Every number in the report is read from an ``AnalysisResults`` object. There
are no hardcoded example figures. The original notebook's report hardcoded
statements such as "The process model represents the real log accurately"
and named the wrong conformance method, and this module exists to prevent that.

Statements about timing are always qualified by the timestamp provenance, so a
report built from synthetic data cannot be mistaken for a hospital finding.
"""

from datetime import datetime

import pandas as pd

from . import config
from .performance_analysis import slowest_transitions
from .variant_analysis import format_variant


def _markdown_table(frame: pd.DataFrame, float_format: str = "{:.2f}") -> str:
    """Render a small DataFrame as a Markdown table (no extra dependency needed)."""
    def cell(value) -> str:
        if isinstance(value, float):
            return "" if pd.isna(value) else float_format.format(value)
        return str(value).replace("|", "/")

    header = "| " + " | ".join(map(str, frame.columns)) + " |"
    divider = "| " + " | ".join("---" for _ in frame.columns) + " |"
    rows = ["| " + " | ".join(cell(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, divider, *rows])


def build_report(results) -> str:
    """Create the Markdown analysis report.

    Args:
        results: An ``AnalysisResults`` object from ``pipeline.run_analysis``.

    Returns:
        The report as a Markdown string.
    """
    counts = results.preparation.counts
    vs = results.variant_summary
    lines = [
        "# Discharge Process Mining: Analysis Report",
        "",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M}  ",
        f"Source: `{results.source}`  ",
        f"Timestamp provenance: **{results.timestamp_provenance}**: "
        f"{config.TIMESTAMP_PROVENANCE_OPTIONS[results.timestamp_provenance]}  ",
        f"Event ordering within cases: **{results.order_by}**",
        "",
        "## 1. Records",
        "",
        f"- Loaded: {counts['loaded']:,} rows",
        f"- Rejected: {counts['rejected']:,} rows (listed with reasons in `rejected_records.csv`)",
    ]
    for key, value in counts.items():
        if key.startswith("rejected_"):
            lines.append(f"  - {key.removeprefix('rejected_')}: {value:,}")
    lines += [
        f"- Retained and analysed: {counts['retained']:,} events in {vs['n_cases']:,} cases",
        "",
        "## 2. Data-quality checks",
        "",
        _markdown_table(results.validation.to_frame()[["check", "count", "unit", "handling"]]),
        "",
        "## 3. Process structure",
        "",
        f"- Distinct activities: {len(results.activity_frequency)}",
        f"- Distinct variants: {vs['n_variants']:,}",
        f"- Most frequent variant covers {vs['top_variant_pct']:.1f}% of cases; "
        f"the top 10 cover {vs['top10_pct']:.1f}%.",
        f"- Variants seen only once: {vs['n_rare_variants']:,} ({vs['rare_case_pct']:.1f}% of cases)",
        "",
        "Top 5 variants:",
        "",
    ]
    top = results.variants.head(5)
    lines.append(_markdown_table(pd.DataFrame({
        "variant": top["variant_id"],
        "cases": top["case_count"],
        "% of cases": top["case_pct"],
        "path": [format_variant(a) for a in top["activities"]],
    })))
    lines += ["", "## 4. Performance", ""]

    if results.performance_available:
        d = results.duration_summary
        lines += [
            f"Case duration (first to last event), {d['n_valid']:,} valid cases "
            f"(excluded: {d['n_single_event']} single-event, {d['n_negative']} negative, {d['n_missing']} missing):",
            "",
            f"- Median {d['median']:.2f} h, mean {d['mean']:.2f} h, 90th percentile {d['p90']:.2f} h, "
            f"range {d['min']:.2f} to {d['max']:.2f} h",
            "",
            "Longest median time between consecutive events (waiting plus work on the next step; "
            f"not activity processing time), transitions seen at least {config.MIN_TRANSITION_COUNT} times:",
            "",
            _markdown_table(slowest_transitions(results.transition_gap_summary, top_n=5)[
                ["source", "target", "count", "median_hours", "p90_hours", "n_negative"]]),
        ]
        if results.timestamp_provenance != "original":
            lines += ["", "> These timings come from **synthetic** timestamps. They demonstrate the "
                          "method and must not be read as real hospital performance."]
    else:
        lines.append("Not established. " + " ".join(n for n in results.notes if "Performance" in n))

    lines += ["", "## 5. Conformance", ""]
    if results.conformance_metrics is not None:
        m = results.conformance_metrics
        lines += [
            "Reference model: the sequential activity order in `config.EXPECTED_ACTIVITIES` "
            "(the original data's dominant path, **not** an approved SOP).",
            "",
            f"- Token-based replay: {m['perc_fit_traces']:.1f}% of cases fit perfectly; "
            f"average case fitness {m['average_trace_fitness']:.3f}; log fitness {m['log_fitness']:.3f}",
        ]
        if results.vocabulary["only_in_log"] or results.vocabulary["only_in_model"]:
            lines.append(f"- Vocabulary mismatch: only in log {results.vocabulary['only_in_log']}, "
                         f"only in model {results.vocabulary['only_in_model']}")
    else:
        lines.append("Not performed. " + " ".join(n for n in results.notes if "Conformance" in n))

    lines += [
        "",
        "## 6. Limitations",
        "",
        "- Only one timestamp per event is available, so activity processing times cannot be measured.",
        "- No independent reference process (SOP) is available; conformance shows agreement with "
        "the usual path, not compliance.",
        "- See `docs/findings_and_limitations.md` for the full discussion.",
        "",
    ]
    return "\n".join(lines)
