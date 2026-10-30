"""Turn raw event records into a clean, consistently ordered event log.

Responsibilities:

* rename source columns to the internal names in ``config``;
* parse timestamps into real datetime values;
* apply the documented cleaning rules and keep every rejected row, with
  its reason, so nothing disappears silently;
* order events consistently within each case.

What this module deliberately does NOT do: it never invents, shifts or
fills in timestamps, and it never drops events just because they produce
an inconvenient result such as a negative duration.
"""

from dataclasses import dataclass, field

import pandas as pd

from . import config

ORDER_BY_TIMESTAMP = "timestamp"
ORDER_BY_FILE = "file_order"


@dataclass
class PreparationResult:
    """Output of :func:`prepare_event_log`.

    Attributes:
        events: The retained events, ordered within each case.
        rejected: Rows that were removed, with a ``rejection_reason`` column.
        counts: Record counts for the audit trail: loaded, rejected (total
            and per reason) and retained.
        order_by: How events were ordered within each case.
    """

    events: pd.DataFrame
    rejected: pd.DataFrame
    counts: dict[str, int] = field(default_factory=dict)
    order_by: str = ORDER_BY_TIMESTAMP


def standardize_columns(df: pd.DataFrame, column_map: dict[str, str] | None = None) -> pd.DataFrame:
    """Rename source columns to the internal names used by the project.

    Args:
        df: Raw event table.
        column_map: Mapping from source name to internal name. Defaults to
            ``config.SOURCE_COLUMN_MAP``. Columns not in the map are kept
            unchanged.

    Returns:
        A renamed copy; the input is not modified.
    """
    return df.rename(columns=column_map or config.SOURCE_COLUMN_MAP)


def parse_timestamps(
    series: pd.Series,
    timestamp_format: str | None = None,
    utc: bool = False,
) -> pd.Series:
    """Convert text timestamps to pandas datetimes.

    Values that cannot be parsed become ``NaT`` (missing) instead of raising
    an error, so that the validation step can count them.

    Timezones: the original dataset has no timezone information, so by
    default times are treated as naive local clock times. Set ``utc=True``
    if the source contains UTC offsets; all values are then converted to UTC.

    Args:
        series: Timestamp values (text or already datetime).
        timestamp_format: Optional explicit format such as
            ``"%Y-%m-%d %H:%M:%S"``. Recommended for real data, because
            inferred formats can misread day/month order.
        utc: Whether to convert to timezone-aware UTC values.

    Returns:
        A datetime Series aligned with the input.
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    cleaned = series.astype("string").str.strip()
    return pd.to_datetime(cleaned, format=timestamp_format, errors="coerce", utc=utc)


def _blank(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype(str).str.strip().eq("")


def prepare_event_log(
    raw: pd.DataFrame,
    order_by: str = ORDER_BY_TIMESTAMP,
    drop_exact_duplicates: bool = False,
    timestamp_format: str | None = None,
    column_map: dict[str, str] | None = None,
) -> PreparationResult:
    """Clean and order raw event records.

    Cleaning rules, applied in this order (each row gets the first reason
    that applies):

    1. ``missing_case_id``: the row has no case identifier.
    2. ``missing_activity``: the row has no activity name.
    3. ``missing_timestamp`` / ``invalid_timestamp``: applied only when
       ``order_by="timestamp"``, because such rows cannot be placed in time.
    4. ``exact_duplicate``: only when ``drop_exact_duplicates=True``. The
       first occurrence is kept.

    Ordering:

    * ``"timestamp"`` (standard): sort by case, then timestamp. Rows with the
      same timestamp keep their source-file order (a stable sort), so the
      result is reproducible.
    * ``"file_order"``: keep the source row order within each case. Use this
      only when timestamps are known to be unreliable *and* you have reason
      to trust that the file was written in event order. Timestamps are still
      parsed but are not used for ordering.

    Args:
        raw: Raw table as returned by ``load_event_data``.
        order_by: ``"timestamp"`` or ``"file_order"``.
        drop_exact_duplicates: Remove rows identical in case, activity and
            timestamp to an earlier row.
        timestamp_format: Optional explicit timestamp format.
        column_map: Optional source-to-internal column mapping.

    Returns:
        A PreparationResult with retained events, rejected rows and counts.

    Raises:
        ValueError: If required columns are missing or ``order_by`` is unknown.
    """
    if order_by not in (ORDER_BY_TIMESTAMP, ORDER_BY_FILE):
        raise ValueError(f"order_by must be '{ORDER_BY_TIMESTAMP}' or '{ORDER_BY_FILE}', got '{order_by}'.")

    df = standardize_columns(raw, column_map).copy()
    missing = [column for column in config.REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s): {missing}. Found: {list(df.columns)}.")

    # Remember where each row came from before anything is filtered or sorted.
    df[config.SOURCE_ROW_COL] = range(len(df))
    raw_timestamp = df[config.TIMESTAMP_COL]
    df[config.TIMESTAMP_COL] = parse_timestamps(raw_timestamp, timestamp_format)
    for column in (config.CASE_COL, config.ACTIVITY_COL):
        df[column] = df[column].astype("string").str.strip()

    reason = pd.Series(pd.NA, index=df.index, dtype="string")

    def reject(mask: pd.Series, label: str) -> None:
        # Only label rows that do not already have an earlier reason.
        reason[mask & reason.isna()] = label

    reject(_blank(df[config.CASE_COL]), "missing_case_id")
    reject(_blank(df[config.ACTIVITY_COL]), "missing_activity")
    if order_by == ORDER_BY_TIMESTAMP:
        reject(_blank(raw_timestamp), "missing_timestamp")
        reject(df[config.TIMESTAMP_COL].isna(), "invalid_timestamp")
    if drop_exact_duplicates:
        reject(df.duplicated(subset=config.REQUIRED_COLUMNS), "exact_duplicate")

    rejected = df[reason.notna()].copy()
    rejected["rejection_reason"] = reason[reason.notna()]
    # Keep the original text so rejected timestamps can be inspected as recorded.
    rejected["timestamp_as_recorded"] = raw_timestamp[reason.notna()]

    events = df[reason.isna()].copy()
    sort_keys = [config.CASE_COL, config.SOURCE_ROW_COL]
    if order_by == ORDER_BY_TIMESTAMP:
        sort_keys = [config.CASE_COL, config.TIMESTAMP_COL, config.SOURCE_ROW_COL]
    events = events.sort_values(sort_keys, kind="stable").reset_index(drop=True)

    counts = {"loaded": len(df), "rejected": len(rejected), "retained": len(events)}
    counts.update({f"rejected_{label}": int(n) for label, n in rejected["rejection_reason"].value_counts().items()})

    return PreparationResult(events=events, rejected=rejected.reset_index(drop=True), counts=counts, order_by=order_by)
