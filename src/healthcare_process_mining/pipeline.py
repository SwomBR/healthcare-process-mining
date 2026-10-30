"""End-to-end analysis pipeline.

Runs the steps in a fixed order and keeps every intermediate result:

    load -> validate -> prepare -> discover -> variants
         -> performance (only if timestamps allow) -> conformance -> report

The ``timestamp_provenance`` argument is the key methodological safeguard.
It forces the caller to state where the timestamps came from, and it decides
whether performance results are findings, illustrations, or not computed at
all (see ``config.TIMESTAMP_PROVENANCE_OPTIONS``).
"""

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import config
from .conformance_checking import build_sequential_net, token_replay, vocabulary_check
from .data_loader import load_event_data
from .data_preparation import ORDER_BY_FILE, ORDER_BY_TIMESTAMP, PreparationResult, prepare_event_log, standardize_columns
from .data_validation import ValidationReport, validate_event_log
from .performance_analysis import (
    case_durations,
    long_running_cases,
    slowest_transitions,
    summarize_durations,
    transition_gap_summary,
    transition_gaps,
)
from .process_discovery import activity_frequency, compute_dfg, start_end_activities
from .variant_analysis import variant_summary, variant_table


@dataclass
class AnalysisResults:
    """Everything the pipeline computed, ready for reporting or the notebook.

    Performance fields are None when performance analysis was skipped, and
    conformance fields are None when no usable reference model was given.
    """

    source: str
    timestamp_provenance: str
    order_by: str
    validation: ValidationReport
    preparation: PreparationResult
    activity_frequency: pd.DataFrame
    dfg: pd.DataFrame
    start_activities: pd.Series
    end_activities: pd.Series
    variants: pd.DataFrame
    variant_summary: dict
    case_durations: pd.DataFrame | None = None
    duration_summary: dict | None = None
    long_running_cases: pd.DataFrame | None = None
    transition_gap_summary: pd.DataFrame | None = None
    vocabulary: dict | None = None
    conformance_metrics: dict | None = None
    conformance_per_case: pd.DataFrame | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def performance_available(self) -> bool:
        return self.case_durations is not None


def run_analysis(
    data: pd.DataFrame | str | Path,
    timestamp_provenance: str,
    order_by: str | None = None,
    reference_activities: list[str] | None = None,
    drop_exact_duplicates: bool = False,
    timestamp_format: str | None = config.TIMESTAMP_FORMAT,
) -> AnalysisResults:
    """Run the full analysis on one event log.

    Args:
        data: A path to a CSV file, or an already loaded raw DataFrame.
        timestamp_provenance: ``"original"``, ``"synthetic"`` or ``"unreliable"``.
        order_by: ``"timestamp"`` or ``"file_order"``. Defaults to
            ``"file_order"`` when timestamps are unreliable (sorting by
            random times would scramble the sequence), else ``"timestamp"``.
        reference_activities: Ordered activity list for the sequential
            reference model. If None, conformance checking is skipped.
        drop_exact_duplicates: Passed to ``prepare_event_log``.
        timestamp_format: Explicit timestamp format; None lets pandas infer it.

    Returns:
        An AnalysisResults object.

    Raises:
        ValueError: For an unknown provenance, or if the data fails a
            blocking validation check (missing columns or no rows).
    """
    if timestamp_provenance not in config.TIMESTAMP_PROVENANCE_OPTIONS:
        raise ValueError(f"timestamp_provenance must be one of {list(config.TIMESTAMP_PROVENANCE_OPTIONS)}.")
    if order_by is None:
        order_by = ORDER_BY_FILE if timestamp_provenance == "unreliable" else ORDER_BY_TIMESTAMP

    source = str(data) if not isinstance(data, pd.DataFrame) else "in-memory DataFrame"
    raw = data if isinstance(data, pd.DataFrame) else load_event_data(data)

    validation = validate_event_log(standardize_columns(raw), config.EXPECTED_ACTIVITIES, timestamp_format)
    if validation.has_blocking_errors:
        raise ValueError(f"Data cannot be analysed: missing columns {validation.missing_columns} "
                         f"or no rows ({validation.n_rows}).")

    preparation = prepare_event_log(raw, order_by=order_by, drop_exact_duplicates=drop_exact_duplicates,
                                    timestamp_format=timestamp_format)
    events = preparation.events
    starts, ends = start_end_activities(events)
    variants = variant_table(events)

    results = AnalysisResults(
        source=source, timestamp_provenance=timestamp_provenance, order_by=order_by,
        validation=validation, preparation=preparation,
        activity_frequency=activity_frequency(events), dfg=compute_dfg(events),
        start_activities=starts, end_activities=ends,
        variants=variants, variant_summary=variant_summary(variants),
    )

    if timestamp_provenance == "unreliable":
        results.notes.append("Performance analysis skipped: timestamps are marked as unreliable.")
    elif order_by == ORDER_BY_FILE:
        results.notes.append("Performance analysis skipped: events are in file order, so durations "
                             "would mix ordering errors with real time differences.")
    else:
        durations = case_durations(events)
        results.case_durations = durations
        results.duration_summary = summarize_durations(durations)
        results.long_running_cases = long_running_cases(durations)
        results.transition_gap_summary = transition_gap_summary(transition_gaps(events))

    if reference_activities:
        vocabulary = vocabulary_check(events, reference_activities)
        results.vocabulary = vocabulary
        if vocabulary["shared"]:
            net, initial, final = build_sequential_net(reference_activities)
            results.conformance_metrics, results.conformance_per_case = token_replay(events, net, initial, final)
        else:
            results.notes.append("Conformance skipped: no activity names are shared by the log and the model.")

    return results


def write_outputs(results: AnalysisResults, output_dir: str | Path) -> dict[str, Path]:
    """Write tables, figures and the Markdown report for a finished analysis.

    Args:
        results: Output of :func:`run_analysis`.
        output_dir: Folder to write into; ``reports/`` and ``figures/`` are
            created inside it.

    Returns:
        A dict mapping a short name to each written file.
    """
    from . import visualization as viz
    from .reporting import build_report

    output_dir = Path(output_dir)
    reports, figures = output_dir / "reports", output_dir / "figures"
    reports.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    def table(name: str, frame: pd.DataFrame) -> None:
        path = reports / f"{name}.csv"
        frame.to_csv(path, index=False)
        written[name] = path

    table("data_quality_checks", results.validation.to_frame())
    table("rejected_records", results.preparation.rejected)
    table("activity_frequency", results.activity_frequency)
    table("directly_follows", results.dfg)
    variants = results.variants.copy()
    variants["activities"] = variants["activities"].map(" > ".join)
    table("variants", variants)

    note = config.TIMESTAMP_PROVENANCE_OPTIONS[results.timestamp_provenance]
    order = config.EXPECTED_ACTIVITIES
    written["fig_activity_frequency"] = viz.save_figure(
        viz.plot_activity_frequency(results.activity_frequency), figures / "activity_frequency.png")
    written["fig_variants"] = viz.save_figure(viz.plot_variant_coverage(results.variants), figures / "top_variants.png")
    written["fig_dfg_matrix"] = viz.save_figure(viz.plot_dfg_matrix(results.dfg, order), figures / "dfg_matrix.png")

    if results.performance_available:
        table("case_durations", results.case_durations)
        table("transition_gaps", results.transition_gap_summary)
        written["fig_case_durations"] = viz.save_figure(
            viz.plot_case_duration_histogram(results.case_durations, results.duration_summary, note),
            figures / "case_duration_distribution.png")
        written["fig_transition_gaps"] = viz.save_figure(
            viz.plot_transition_gaps(slowest_transitions(results.transition_gap_summary),
                                     provenance_note=f"Transitions seen at least {config.MIN_TRANSITION_COUNT} "
                                                     f"times. {note}"),
            figures / "transition_gaps.png")

    if results.conformance_per_case is not None:
        table("conformance_per_case", results.conformance_per_case)

    report_path = reports / "analysis_report.md"
    report_path.write_text(build_report(results), encoding="utf-8")
    written["report"] = report_path
    return written
