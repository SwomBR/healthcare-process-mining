"""Tests for loading event data from disk."""

import pytest

from healthcare_process_mining.data_loader import load_event_data


def test_loads_csv_and_keeps_values_as_text(tmp_path):
    path = tmp_path / "events.csv"
    path.write_text("Case ID,Activity,Timestamp\n00123,Order,2024-01-01 08:00:00\n", encoding="utf-8")

    df = load_event_data(path)

    assert list(df.columns) == ["Case ID", "Activity", "Timestamp"]
    assert len(df) == 1
    # Read as text, so the leading zeros of the ID survive.
    assert df.loc[0, "Case ID"] == "00123"


def test_handles_byte_order_mark_and_padded_headers(tmp_path):
    path = tmp_path / "events.csv"
    path.write_text("Case ID, Activity ,Timestamp\nA,Order,2024-01-01\n", encoding="utf-8-sig")

    df = load_event_data(path)

    assert list(df.columns) == ["Case ID", "Activity", "Timestamp"]


def test_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        load_event_data(tmp_path / "does_not_exist.csv")


def test_unsupported_extension_raises_value_error(tmp_path):
    path = tmp_path / "events.xlsx"
    path.write_bytes(b"not really excel")
    with pytest.raises(ValueError, match="Unsupported file type"):
        load_event_data(path)


def test_empty_file_raises_value_error(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        load_event_data(path)
