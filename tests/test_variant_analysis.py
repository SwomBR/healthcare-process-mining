"""Tests for process-variant counting."""

import pandas as pd
import pytest

from healthcare_process_mining.variant_analysis import format_variant, variant_summary, variant_table


def make_events(traces: dict[str, list[str]]) -> pd.DataFrame:
    rows = [(case, activity) for case, activities in traces.items() for activity in activities]
    return pd.DataFrame(rows, columns=["case_id", "activity"])


def test_variants_are_counted_and_ranked():
    events = make_events({
        "1": ["A", "B", "C"],
        "2": ["A", "B", "C"],
        "3": ["A", "C"],
        "4": ["A", "B", "C"],
    })

    table = variant_table(events)

    assert len(table) == 2
    assert table.iloc[0]["activities"] == ("A", "B", "C")
    assert table.iloc[0]["case_count"] == 3
    assert table.iloc[0]["case_pct"] == pytest.approx(75.0)
    assert table.iloc[1]["n_activities"] == 2
    assert table["cumulative_pct"].iloc[-1] == pytest.approx(100.0)
    assert table["variant_id"].tolist() == [1, 2]


def test_order_matters_for_variants():
    table = variant_table(make_events({"1": ["A", "B"], "2": ["B", "A"]}))
    assert len(table) == 2


def test_ties_are_broken_reproducibly():
    table = variant_table(make_events({"1": ["Z"], "2": ["A"]}))
    assert table["activities"].tolist() == [("A",), ("Z",)]


def test_single_event_cases_form_their_own_variant():
    table = variant_table(make_events({"1": ["A"], "2": ["A", "B"]}))
    assert ("A",) in table["activities"].tolist()


def test_summary_counts_rare_variants():
    events = make_events({"1": ["A", "B"], "2": ["A", "B"], "3": ["A"], "4": ["B"]})
    summary = variant_summary(variant_table(events))

    assert summary["n_cases"] == 4
    assert summary["n_variants"] == 3
    assert summary["top_variant_pct"] == pytest.approx(50.0)
    assert summary["n_rare_variants"] == 2
    assert summary["rare_case_pct"] == pytest.approx(50.0)


def test_empty_log():
    table = variant_table(make_events({}))
    assert table.empty
    assert variant_summary(table)["n_variants"] == 0


def test_format_variant_truncates():
    assert format_variant(("A", "B")) == "A > B"
    assert format_variant(("Alpha", "Beta", "Gamma"), max_length=10) == "Alpha >..."
