"""Tests for cleaning rules and event ordering."""

import pandas as pd
import pytest

from healthcare_process_mining.data_preparation import parse_timestamps, prepare_event_log

FMT = "%Y-%m-%d %H:%M:%S"


def test_events_are_sorted_by_case_then_timestamp(raw_log):
    result = prepare_event_log(raw_log, timestamp_format=FMT)
    case_a = result.events[result.events["case_id"] == "A"]

    assert case_a["activity"].tolist() == ["Order", "Med", "Leave"]
    assert pd.api.types.is_datetime64_any_dtype(result.events["timestamp"])
    assert result.counts == {"loaded": 6, "rejected": 0, "retained": 6}


def test_file_order_mode_keeps_source_row_order(raw_log):
    result = prepare_event_log(raw_log, order_by="file_order", timestamp_format=FMT)
    case_a = result.events[result.events["case_id"] == "A"]

    assert case_a["activity"].tolist() == ["Leave", "Order", "Med"]


def test_source_row_is_preserved_for_traceability(raw_log):
    result = prepare_event_log(raw_log, timestamp_format=FMT)
    first = result.events.iloc[0]

    # Case A's first event in time ("Order") was row 1 of the source file.
    assert (first["case_id"], first["activity"], first["source_row"]) == ("A", "Order", 1)


def test_rows_with_problems_are_rejected_with_reasons_not_dropped_silently(raw_log):
    raw = raw_log.copy()
    raw.loc[0, "Case ID"] = None
    raw.loc[1, "Activity"] = ""
    raw.loc[2, "Timestamp"] = None
    raw.loc[3, "Timestamp"] = "not a date"

    result = prepare_event_log(raw, timestamp_format=FMT)

    assert result.counts["loaded"] == 6
    assert result.counts["retained"] == 2
    assert result.counts["rejected"] == 4
    assert sorted(result.rejected["rejection_reason"]) == [
        "invalid_timestamp", "missing_activity", "missing_case_id", "missing_timestamp"]
    # The rejected timestamp is kept exactly as recorded, for inspection.
    bad = result.rejected[result.rejected["rejection_reason"] == "invalid_timestamp"]
    assert bad["timestamp_as_recorded"].iloc[0] == "not a date"


def test_missing_timestamps_are_never_filled_in(raw_log):
    raw = raw_log.copy()
    raw.loc[2, "Timestamp"] = None

    result = prepare_event_log(raw, order_by="file_order", timestamp_format=FMT)

    # In file-order mode the row is kept, and its timestamp stays missing.
    med = result.events[result.events["activity"] == "Med"]
    assert len(med) == 1
    assert med["timestamp"].isna().all()


def test_each_row_gets_only_its_first_rejection_reason(raw_log):
    raw = raw_log.copy()
    raw.loc[0, ["Case ID", "Timestamp"]] = [None, None]

    result = prepare_event_log(raw, timestamp_format=FMT)

    assert result.rejected["rejection_reason"].tolist() == ["missing_case_id"]


def test_exact_duplicates_kept_by_default_and_dropped_on_request(raw_log):
    raw = pd.concat([raw_log, raw_log.iloc[[3]]], ignore_index=True)

    kept = prepare_event_log(raw, timestamp_format=FMT)
    dropped = prepare_event_log(raw, drop_exact_duplicates=True, timestamp_format=FMT)

    assert kept.counts["retained"] == 7
    assert dropped.counts["retained"] == 6
    assert dropped.counts["rejected_exact_duplicate"] == 1


def test_ties_keep_source_order(raw_log):
    raw = raw_log.copy()
    raw.loc[4, "Timestamp"] = raw.loc[3, "Timestamp"]  # B's two events now share a time

    result = prepare_event_log(raw, timestamp_format=FMT)

    assert result.events[result.events["case_id"] == "B"]["activity"].tolist() == ["Order", "Leave"]


def test_missing_required_column_raises(raw_log):
    with pytest.raises(ValueError, match="Missing required column"):
        prepare_event_log(raw_log.drop(columns=["Activity"]))


def test_unknown_order_mode_raises(raw_log):
    with pytest.raises(ValueError, match="order_by"):
        prepare_event_log(raw_log, order_by="alphabetical")


def test_input_dataframe_is_not_modified(raw_log):
    before = raw_log.copy()
    prepare_event_log(raw_log, timestamp_format=FMT)
    pd.testing.assert_frame_equal(raw_log, before)


def test_empty_input_gives_empty_result():
    empty = pd.DataFrame(columns=["Case ID", "Activity", "Timestamp"])
    result = prepare_event_log(empty)
    assert result.events.empty
    assert result.counts == {"loaded": 0, "rejected": 0, "retained": 0}


def test_parse_timestamps_with_utc_offsets():
    parsed = parse_timestamps(pd.Series(["2024-01-01T10:00:00+02:00", "2024-01-01T08:00:00Z"]), utc=True)
    assert parsed.iloc[0] == parsed.iloc[1]
