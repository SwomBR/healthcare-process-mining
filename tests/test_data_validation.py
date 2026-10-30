"""Tests for the data-quality checks."""

import pandas as pd

from healthcare_process_mining.data_validation import (
    find_invalid_timestamps,
    find_order_conflicts,
    validate_event_log,
)


def test_clean_log_reports_zero_problems_except_known_ones(standardized_log):
    report = validate_event_log(standardized_log, expected_activities=["Order", "Med", "Leave"])

    assert not report.has_blocking_errors
    assert report.n_rows == 6
    assert report.n_cases == 3
    for check in ["missing_case_id", "missing_activity", "missing_timestamp",
                  "invalid_timestamp", "exact_duplicate", "unexpected_activity"]:
        assert report.get(check) == 0, check
    # Case A is written out of time order; case C has one event.
    assert report.get("case_order_conflict") == 1
    assert report.get("single_event_case") == 1


def test_missing_columns_block_analysis(standardized_log):
    report = validate_event_log(standardized_log.drop(columns=["timestamp"]))

    assert report.missing_columns == ["timestamp"]
    assert report.has_blocking_errors
    assert report.issues == []


def test_empty_dataset_is_blocking():
    empty = pd.DataFrame(columns=["case_id", "activity", "timestamp"])
    assert validate_event_log(empty).has_blocking_errors


def test_missing_identifiers_and_activities_are_counted(standardized_log):
    df = standardized_log.copy()
    df.loc[0, "case_id"] = None
    df.loc[1, "case_id"] = "   "  # whitespace only counts as missing
    df.loc[2, "activity"] = None

    report = validate_event_log(df)

    assert report.get("missing_case_id") == 2
    assert report.get("missing_activity") == 1


def test_missing_and_invalid_timestamps_are_counted_separately(standardized_log):
    df = standardized_log.copy()
    df.loc[0, "timestamp"] = None
    df.loc[1, "timestamp"] = "2024-02-30 10:00:00"  # 30 February does not exist
    df.loc[2, "timestamp"] = "yesterday"

    report = validate_event_log(df, timestamp_format="%Y-%m-%d %H:%M:%S")

    assert report.get("missing_timestamp") == 1
    assert report.get("invalid_timestamp") == 2


def test_find_invalid_timestamps_ignores_missing_values():
    series = pd.Series(["2024-01-01 08:00:00", None, "bad"])
    assert find_invalid_timestamps(series, "%Y-%m-%d %H:%M:%S").tolist() == [False, False, True]


def test_exact_duplicates_flagged_but_rework_is_not(standardized_log):
    df = pd.concat([standardized_log, standardized_log.iloc[[3]]], ignore_index=True)
    # The same activity again at a later time is rework, not a duplicate.
    rework = pd.DataFrame({"case_id": ["B"], "activity": ["Order"], "timestamp": ["2024-01-02 11:00:00"]})
    df = pd.concat([df, rework], ignore_index=True)

    report = validate_event_log(df)

    assert report.get("exact_duplicate") == 1
    # The duplicate row and its original share a timestamp.
    assert report.get("same_timestamp_in_case") == 2


def test_order_conflict_detects_backwards_rows(standardized_log):
    conflicts = find_order_conflicts(standardized_log)
    assert conflicts.to_dict() == {"A": True, "B": False, "C": False}


def test_unexpected_activities_are_listed(standardized_log):
    report = validate_event_log(standardized_log, expected_activities=["Order", "Leave"])

    assert report.get("unexpected_activity") == 1
    assert report.unexpected_activities == {"Med": 1}


def test_report_converts_to_table(standardized_log):
    table = validate_event_log(standardized_log).to_frame()
    assert {"check", "count", "unit", "rule", "handling"} <= set(table.columns)
