"""Tests for DFG, activity frequency and PM4Py integration."""

import pandas as pd
import pytest

from healthcare_process_mining.data_preparation import prepare_event_log
from healthcare_process_mining.process_discovery import (
    activity_frequency,
    build_event_log,
    compute_dfg,
    discover_petri_net,
    start_end_activities,
)

FMT = "%Y-%m-%d %H:%M:%S"


@pytest.fixture
def events(raw_log):
    return prepare_event_log(raw_log, timestamp_format=FMT).events


def test_dfg_counts_direct_successions_within_cases_only(events):
    dfg = compute_dfg(events)
    edges = {(s, t): c for s, t, c in zip(dfg["source"], dfg["target"], dfg["count"])}

    # A: Order>Med>Leave, B: Order>Leave, C: Order. No edge crosses cases.
    assert edges == {("Order", "Med"): 1, ("Med", "Leave"): 1, ("Order", "Leave"): 1}


def test_activity_frequency_distinguishes_events_and_cases():
    events = pd.DataFrame({"case_id": ["1", "1", "2"], "activity": ["Sign", "Sign", "Sign"]})
    row = activity_frequency(events).iloc[0]
    assert (row["event_count"], row["case_count"]) == (3, 2)


def test_start_and_end_activities(events):
    starts, ends = start_end_activities(events)
    assert starts.to_dict() == {"Order": 3}
    assert ends.to_dict() == {"Leave": 2, "Order": 1}


def test_empty_dfg():
    empty = pd.DataFrame({"case_id": [], "activity": []})
    assert compute_dfg(empty).empty


@pytest.mark.pm4py
def test_event_log_preserves_prepared_order(raw_log):
    """PM4Py must not re-sort events; this is what caused the original negative durations."""
    file_ordered = prepare_event_log(raw_log, order_by="file_order", timestamp_format=FMT).events
    log = build_event_log(file_ordered)
    traces = {t.attributes["concept:name"]: [e["concept:name"] for e in t] for t in log}

    assert len(log) == 3  # len(EventLog) counts CASES, not events
    assert traces["A"] == ["Leave", "Order", "Med"]


@pytest.mark.pm4py
def test_pandas_dfg_matches_pm4py(events):
    import pm4py

    pm4py_dfg, starts, ends = pm4py.discover_dfg(build_event_log(events))
    ours = compute_dfg(events)

    assert {(s, t): c for s, t, c in zip(ours["source"], ours["target"], ours["count"])} == dict(pm4py_dfg)
    assert start_end_activities(events)[0].to_dict() == dict(starts)


@pytest.mark.pm4py
@pytest.mark.parametrize("algorithm", ["inductive", "heuristics"])
def test_discover_petri_net_contains_all_activities(events, algorithm):
    net, initial, final = discover_petri_net(events, algorithm=algorithm)
    labels = {t.label for t in net.transitions if t.label}
    assert labels == {"Order", "Med", "Leave"}
    assert len(initial) == 1 and len(final) == 1


def test_discover_rejects_unknown_algorithm_and_empty_log(events):
    with pytest.raises(ValueError, match="Unknown algorithm"):
        discover_petri_net(events, algorithm="alpha")
    with pytest.raises(ValueError, match="empty"):
        discover_petri_net(events.iloc[0:0])
