"""Data-quality checks for event logs.

Process mining tools such as PM4Py accept almost any table with a case ID,
an activity and a timestamp. They will not warn you if the timestamps are
wrong. This module makes data-quality problems visible *before* analysis.

Every check only reports; nothing is removed or modified here. The rules for
what happens to problem rows are applied (and counted) in
``data_preparation``. Each check records the rule it applies and how the
pipeline handles the affected rows, so the report doubles as documentation.

Expected input: a DataFrame whose columns have already been renamed to the
internal names in ``config`` (``case_id``, ``activity``, ``timestamp``).
Timestamps may still be raw text.
"""

from dataclasses import dataclass, field

import pandas as pd

from . import config
from .data_preparation import parse_timestamps


@dataclass
class ValidationIssue:
    """One data-quality check and its result.

    Attributes:
        check: Short name of the check.
        count: Number of affected rows (or cases, see ``unit``).
        unit: What ``count`` counts: "rows" or "cases".
        rule: The rule being applied, in plain language.
        handling: What the pipeline does with the affected records.
    """

    check: str
    count: int
    unit: str
    rule: str
    handling: str


@dataclass
class ValidationReport:
    """Results of all data-quality checks on one event table.

    Attributes:
        n_rows: Number of rows inspected.
        n_cases: Number of distinct non-missing case IDs.
        missing_columns: Required columns that are absent. If this is not
            empty, the other checks could not run.
        issues: One entry per check that was run (including checks that
            found zero problems, so a clean result is visible too).
        unexpected_activities: Activity name mapped to row count, for
            names not in the expected vocabulary.
    """

    n_rows: int
    n_cases: int
    missing_columns: list[str] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    unexpected_activities: dict[str, int] = field(default_factory=dict)

    @property
    def has_blocking_errors(self) -> bool:
        """True if analysis cannot proceed (missing columns or no rows)."""
        return bool(self.missing_columns) or self.n_rows == 0

    def get(self, check: str) -> int:
        """Return the count for a named check, or 0 if it was not run."""
        for issue in self.issues:
            if issue.check == check:
                return issue.count
        return 0

    def to_frame(self) -> pd.DataFrame:
        """Return the issues as a table, convenient for notebooks and reports."""
        return pd.DataFrame([issue.__dict__ for issue in self.issues])


def find_missing_columns(df: pd.DataFrame, required: list[str]) -> list[str]:
    """Return the required column names that are not present in ``df``."""
    return [column for column in required if column not in df.columns]


def is_blank(series: pd.Series) -> pd.Series:
    """Return a boolean mask of values that are missing or only whitespace."""
    return series.isna() | series.astype(str).str.strip().eq("")


def find_invalid_timestamps(series: pd.Series, timestamp_format: str | None = None) -> pd.Series:
    """Return a mask of values that are present but cannot be parsed as dates.

    Missing values are *not* counted here; they are reported separately so
    that "no timestamp recorded" and "timestamp recorded wrongly" stay
    distinguishable.
    """
    parsed = parse_timestamps(series, timestamp_format)
    return ~is_blank(series) & parsed.isna()


def find_order_conflicts(df: pd.DataFrame, timestamp_format: str | None = None) -> pd.Series:
    """Flag cases whose rows, in file order, are not in chronological order.

    If a tool keeps the file order inside each case (PM4Py 2.7.19 did, in the
    original notebook), then "last event minus first event" can be negative
    for these cases. This was the root cause of the negative case durations
    in the original analysis.

    Args:
        df: Event table in source-file order, with a parseable timestamp column.
        timestamp_format: Optional explicit timestamp format.

    Returns:
        A boolean Series indexed by case ID: True where at least one event
        is earlier than the event recorded before it.
    """
    timestamps = parse_timestamps(df[config.TIMESTAMP_COL], timestamp_format)
    # Compare each event with the previous event of the same case.
    previous = timestamps.groupby(df[config.CASE_COL]).shift()
    goes_backwards = timestamps < previous
    return goes_backwards.groupby(df[config.CASE_COL]).any()


def validate_event_log(
    df: pd.DataFrame,
    expected_activities: list[str] | None = None,
    timestamp_format: str | None = None,
) -> ValidationReport:
    """Run all data-quality checks on an event table.

    Args:
        df: Event table with internal column names, in source-file order.
        expected_activities: Known activity names. If given, other names are
            reported as unexpected. If None, this check is skipped.
        timestamp_format: Optional explicit ``strftime`` format, for example
            ``"%Y-%m-%d %H:%M:%S"``. If None, pandas infers it.

    Returns:
        A ValidationReport. Check ``report.has_blocking_errors`` before
        continuing.
    """
    report = ValidationReport(n_rows=len(df), n_cases=0)
    report.missing_columns = find_missing_columns(df, config.REQUIRED_COLUMNS)
    if report.has_blocking_errors:
        return report

    case = df[config.CASE_COL]
    activity = df[config.ACTIVITY_COL]
    timestamp = df[config.TIMESTAMP_COL]
    report.n_cases = case[~is_blank(case)].nunique()

    def add(check: str, count: int, unit: str, rule: str, handling: str) -> None:
        report.issues.append(ValidationIssue(check, int(count), unit, rule, handling))

    add(
        "missing_case_id", is_blank(case).sum(), "rows",
        "Every event must belong to a case.",
        "Rejected: an event without a case cannot be placed in any trace.",
    )
    add(
        "missing_activity", is_blank(activity).sum(), "rows",
        "Every event must name an activity.",
        "Rejected: an unnamed event cannot be placed in a process model.",
    )
    add(
        "missing_timestamp", is_blank(timestamp).sum(), "rows",
        "Every event should record when it happened.",
        "Rejected when ordering by timestamp; never filled in or estimated.",
    )
    add(
        "invalid_timestamp", find_invalid_timestamps(timestamp, timestamp_format).sum(), "rows",
        "A recorded timestamp must be a valid date-time.",
        "Rejected when ordering by timestamp; never corrected or estimated.",
    )

    # An exact duplicate has the same case, activity and timestamp. A repeated
    # activity at a *different* time is legitimate (e.g. rework) and is not flagged.
    add(
        "exact_duplicate", df.duplicated(subset=config.REQUIRED_COLUMNS).sum(), "rows",
        "Same case, activity and timestamp as an earlier row; usually a double recording.",
        "Flagged and kept by default (dropping is an explicit preparation option).",
    )

    parsed = parse_timestamps(timestamp, timestamp_format)
    tie_mask = parsed.notna() & df.assign(_ts=parsed).duplicated(
        subset=[config.CASE_COL, "_ts"], keep=False
    )
    add(
        "same_timestamp_in_case", tie_mask.sum(), "rows",
        "Events in one case sharing an identical timestamp have an ambiguous order.",
        "Kept; ties are ordered by their position in the source file.",
    )

    add(
        "case_order_conflict", find_order_conflicts(df, timestamp_format).sum(), "cases",
        "Rows of a case, in file order, should not go backwards in time.",
        "Kept; events are re-sorted by timestamp, which removes negative durations "
        "only if the timestamps are trustworthy.",
    )

    events_per_case = case[~is_blank(case)].value_counts()
    add(
        "single_event_case", (events_per_case == 1).sum(), "cases",
        "A case with one event has no duration and no transitions.",
        "Kept for frequency analysis; excluded from duration statistics.",
    )

    if expected_activities is not None:
        known = activity.isin(expected_activities) | is_blank(activity)
        report.unexpected_activities = activity[~known].value_counts().to_dict()
        add(
            "unexpected_activity", (~known).sum(), "rows",
            "Activity names should come from the known vocabulary.",
            "Kept and reported; may be a new activity or a spelling variant.",
        )

    return report
