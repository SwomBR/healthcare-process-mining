"""Tests for duration and transition-gap calculations."""

import math

import pandas as pd
import pytest

from healthcare_process_mining.data_preparation import prepare_event_log
from healthcare_process_mining.performance_analysis import (
    case_durations,
    long_running_cases,
    summarize_durations,
    transition_gap_summary,
    transition_gaps,
)

FMT = "%Y-%m-%d %H:%M:%S"


@pytest.fixture
def events(raw_log):
    return prepare_event_log(raw_log, timestamp_format=FMT).events


def test_case_durations_in_hours(events):
    durations = case_durations(events).set_index("case_id")

    assert durations.loc["A", "duration_hours"] == 5.0  # 08:00 -> 13:00
    assert durations.loc["B", "duration_hours"] == 0.5  # 09:00 -> 09:30
    assert durations.loc["C", "duration_hours"] == 0.0
    assert durations.loc["A", "n_events"] == 3
    assert durations.loc["A", "first_activity"] == "Order"
    assert durations.loc["A", "last_activity"] == "Leave"
    assert durations.loc["C", "is_single_event"]


def test_file_order_reproduces_original_negative_duration(raw_log):
    """Case A's file order is Leave(13:00), Order(08:00), Med(10:00).

    "Last minus first" in that order is 10:00 - 13:00 = -3 h. This is exactly
    how the original notebook produced negative case durations.
    """
    file_ordered = prepare_event_log(raw_log, order_by="file_order", timestamp_format=FMT).events
    durations = case_durations(file_ordered).set_index("case_id")

    assert durations.loc["A", "duration_hours"] == -3.0
    assert durations.loc["A", "is_negative"]


def test_summary_excludes_and_counts_negative_and_single_event_cases(raw_log):
    file_ordered = prepare_event_log(raw_log, order_by="file_order", timestamp_format=FMT).events
    summary = summarize_durations(case_durations(file_ordered))

    assert summary["n_total"] == 3
    assert summary["n_negative"] == 1  # case A
    assert summary["n_single_event"] == 1  # case C
    assert summary["n_valid"] == 1  # only case B
    assert summary["mean"] == 0.5


def test_summary_of_valid_durations(events):
    summary = summarize_durations(case_durations(events))

    assert summary["n_valid"] == 2  # A and B; C is a single event
    assert summary["mean"] == pytest.approx(2.75)
    assert summary["median"] == pytest.approx(2.75)
    assert summary["min"] == 0.5
    assert summary["max"] == 5.0


def test_missing_timestamp_gives_missing_duration_not_zero(raw_log):
    raw = raw_log.copy()
    raw.loc[0, "Timestamp"] = None  # A's last event ("Leave") loses its time
    file_ordered = prepare_event_log(raw, order_by="file_order", timestamp_format=FMT).events
    durations = case_durations(file_ordered).set_index("case_id")

    # In file order A starts with the event that has no time.
    assert math.isnan(durations.loc["A", "duration_hours"])
    assert summarize_durations(durations.reset_index())["n_missing"] == 1


def test_empty_inputs_give_empty_results():
    empty = pd.DataFrame({"case_id": [], "activity": [], "timestamp": pd.to_datetime([])})
    assert case_durations(empty).empty
    summary = summarize_durations(case_durations(empty))
    assert summary["n_valid"] == 0 and math.isnan(summary["mean"])
    assert transition_gap_summary(transition_gaps(empty)).empty


def test_transition_gaps_list_consecutive_pairs(events):
    gaps = transition_gaps(events)

    # A contributes 2 transitions, B 1 and C none.
    assert len(gaps) == 3
    pairs = list(zip(gaps["case_id"], gaps["source"], gaps["target"], gaps["gap_hours"]))
    assert ("A", "Order", "Med", 2.0) in pairs
    assert ("A", "Med", "Leave", 3.0) in pairs
    assert ("B", "Order", "Leave", 0.5) in pairs


def test_transition_summary_ranks_by_median(events):
    summary = transition_gap_summary(transition_gaps(events))

    assert summary.iloc[0][["source", "target"]].tolist() == ["Med", "Leave"]
    assert summary.iloc[0]["median_hours"] == 3.0
    assert summary["count"].sum() == 3
    assert summary["n_negative"].sum() == 0


def test_long_running_cases(events):
    long_cases = long_running_cases(case_durations(events), quantile=0.5)
    assert long_cases["case_id"].tolist() == ["A"]


def test_long_running_rejects_bad_quantile(events):
    with pytest.raises(ValueError):
        long_running_cases(case_durations(events), quantile=1.5)


def test_slowest_transitions_ignores_rare_transitions():
    summary = pd.DataFrame({
        "source": ["X", "A"], "target": ["Y", "B"], "count": [1, 50],
        "n_negative": [0, 0], "median_hours": [9.0, 2.0],
        "mean_hours": [9.0, 2.0], "p90_hours": [9.0, 3.0], "max_hours": [9.0, 4.0],
    })
    from healthcare_process_mining.performance_analysis import slowest_transitions

    ranked = slowest_transitions(summary, min_count=10)
    assert ranked[["source", "target"]].values.tolist() == [["A", "B"]]
