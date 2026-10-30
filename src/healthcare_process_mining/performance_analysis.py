"""Time-based (performance) analysis of an event log.

Three different time measures are often confused. This module keeps them
separate:

* **Case duration**: time from the first to the last recorded event of a
  case.
* **Transition gap** (time between consecutive events): time from one event
  to the next event in the same case. It includes waiting, hand-over and
  any work on the second activity. It is NOT the processing time of either
  activity.
* **Activity processing time**: how long an activity itself took. This needs
  a start *and* an end timestamp per activity. The discharge dataset has only
  one timestamp per event, so processing time cannot be measured, and this
  module does not pretend to.

All durations are returned in hours (``float``) to avoid mixing units.

Negative values: if events were ordered by timestamp, durations cannot be
negative. If they were kept in file order (``order_by="file_order"``), a
negative value means the file order and the timestamps disagree. Negative
values are never dropped silently; they are flagged, counted and excluded
from the summary statistics, and that exclusion is reported.

These results are only as meaningful as the timestamps. See
``docs/findings_and_limitations.md``.
"""

import pandas as pd

from . import config

SECONDS_PER_HOUR = 3600


def case_durations(events: pd.DataFrame) -> pd.DataFrame:
    """Calculate the duration of every case.

    The duration is "timestamp of the last event minus timestamp of the
    first event", using the order of the rows in ``events``. This matches
    PM4Py's ``get_all_case_durations``, which makes the comparison with the
    original notebook direct.

    Args:
        events: Prepared events with parsed timestamps, ordered within each case.

    Returns:
        One row per case with ``case_id``, ``n_events``, ``first_activity``,
        ``last_activity``, ``start``, ``end``, ``duration_hours``,
        ``is_single_event`` and ``is_negative``. Cases with a missing first
        or last timestamp get ``NaN`` duration.
    """
    columns = ["case_id", "n_events", "first_activity", "last_activity", "start", "end",
               "duration_hours", "is_single_event", "is_negative"]
    if events.empty:
        return pd.DataFrame(columns=columns)

    grouped = events.groupby(config.CASE_COL, sort=True)
    result = pd.DataFrame({
        "n_events": grouped.size(),
        "first_activity": grouped[config.ACTIVITY_COL].first(),
        "last_activity": grouped[config.ACTIVITY_COL].last(),
        # iloc takes the true first/last rows; .first()/.last() would skip missing times.
        "start": grouped[config.TIMESTAMP_COL].agg(lambda times: times.iloc[0]),
        "end": grouped[config.TIMESTAMP_COL].agg(lambda times: times.iloc[-1]),
    })
    result["duration_hours"] = (result["end"] - result["start"]).dt.total_seconds() / SECONDS_PER_HOUR
    result["is_single_event"] = result["n_events"] == 1
    result["is_negative"] = result["duration_hours"] < 0
    return result.rename_axis("case_id").reset_index()[columns]


def summarize_durations(durations: pd.DataFrame, value_column: str = "duration_hours") -> dict[str, float]:
    """Summarise a duration column, reporting what was excluded and why.

    Statistics use only *valid* values: not missing, not negative and, for
    case durations, not from single-event cases (which always have zero
    duration and would pull the average down).

    Args:
        durations: Output of :func:`case_durations` or :func:`transition_gaps`.
        value_column: Column holding the durations in hours.

    Returns:
        Counts (``n_total``, ``n_valid``, ``n_missing``, ``n_negative``,
        ``n_single_event``) and statistics in hours (``mean``, ``median``,
        ``p90``, ``min``, ``max``). The statistics are ``NaN`` if no value is valid.
    """
    values = durations[value_column]
    single = durations["is_single_event"] if "is_single_event" in durations else pd.Series(False, index=durations.index)
    missing = values.isna()
    negative = values < 0
    valid = values[~missing & ~negative & ~single]
    return {
        "n_total": len(values),
        "n_valid": len(valid),
        "n_missing": int(missing.sum()),
        "n_negative": int(negative.sum()),
        "n_single_event": int(single.sum()),
        "mean": float(valid.mean()) if len(valid) else float("nan"),
        "median": float(valid.median()) if len(valid) else float("nan"),
        "p90": float(valid.quantile(0.9)) if len(valid) else float("nan"),
        "min": float(valid.min()) if len(valid) else float("nan"),
        "max": float(valid.max()) if len(valid) else float("nan"),
    }


def long_running_cases(durations: pd.DataFrame, quantile: float = config.LONG_RUNNING_QUANTILE) -> pd.DataFrame:
    """Return cases whose duration is above the given quantile, longest first.

    The threshold is calculated from valid durations only (see
    :func:`summarize_durations`).

    Args:
        durations: Output of :func:`case_durations`.
        quantile: Threshold between 0 and 1. For example, 0.9 returns the
            slowest 10% of cases.

    Raises:
        ValueError: If ``quantile`` is outside 0 to 1.
    """
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between 0 and 1.")
    valid = durations[(durations["duration_hours"] >= 0) & ~durations["is_single_event"]]
    if valid.empty:
        return valid
    threshold = valid["duration_hours"].quantile(quantile)
    return valid[valid["duration_hours"] > threshold].sort_values("duration_hours", ascending=False)


def transition_gaps(events: pd.DataFrame) -> pd.DataFrame:
    """List every pair of consecutive events within a case, with the time between them.

    Args:
        events: Prepared events with parsed timestamps, ordered within each case.

    Returns:
        One row per transition with ``case_id``, ``source``, ``target``
        and ``gap_hours``. A case with n events contributes n - 1 rows.
    """
    case = events[config.CASE_COL]
    next_activity = events.groupby(case)[config.ACTIVITY_COL].shift(-1)
    next_time = events.groupby(case)[config.TIMESTAMP_COL].shift(-1)
    has_next = next_activity.notna()
    gaps = pd.DataFrame({
        "case_id": case[has_next],
        "source": events.loc[has_next, config.ACTIVITY_COL],
        "target": next_activity[has_next],
        "gap_hours": (next_time - events[config.TIMESTAMP_COL])[has_next].dt.total_seconds() / SECONDS_PER_HOUR,
    })
    return gaps.reset_index(drop=True)


def transition_gap_summary(gaps: pd.DataFrame) -> pd.DataFrame:
    """Summarise transition gaps per (source, target) pair.

    The ranking uses the **median**, not the mean. Gaps are usually skewed
    (a few very long waits), and a mean ranking, as in the original notebook,
    is easily dominated by outliers.

    Args:
        gaps: Output of :func:`transition_gaps`.

    Returns:
        One row per transition with ``count``, ``n_negative`` and the
        ``median_hours``, ``mean_hours``, ``p90_hours`` and ``max_hours`` of
        the non-negative gaps, sorted by median descending.
    """
    columns = ["source", "target", "count", "n_negative", "median_hours", "mean_hours", "p90_hours", "max_hours"]
    if gaps.empty:
        return pd.DataFrame(columns=columns)

    valid = gaps[gaps["gap_hours"] >= 0]
    stats = valid.groupby(["source", "target"])["gap_hours"].agg(
        median_hours="median", mean_hours="mean",
        p90_hours=lambda values: values.quantile(0.9), max_hours="max",
    )
    counts = gaps.groupby(["source", "target"]).agg(
        count=("gap_hours", "size"),
        n_negative=("gap_hours", lambda values: int((values < 0).sum())),
    )
    summary = counts.join(stats).reset_index()
    return summary.sort_values("median_hours", ascending=False, na_position="last").reset_index(drop=True)[columns]


def slowest_transitions(gap_summary: pd.DataFrame, min_count: int = config.MIN_TRANSITION_COUNT,
                        top_n: int = config.TOP_N) -> pd.DataFrame:
    """Return the transitions with the longest median gap that have enough observations.

    Args:
        gap_summary: Output of :func:`transition_gap_summary` (sorted by median).
        min_count: Minimum number of observations for a transition to be ranked.
        top_n: Number of rows to return.
    """
    return gap_summary[gap_summary["count"] >= min_count].head(top_n).reset_index(drop=True)
