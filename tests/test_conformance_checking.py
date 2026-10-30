"""Tests for conformance checking."""

import pandas as pd
import pytest

from healthcare_process_mining.conformance_checking import (
    build_sequential_net,
    check_precedence,
    model_activities,
    token_replay,
    vocabulary_check,
)


def make_events(traces: dict[str, list[str]]) -> pd.DataFrame:
    rows = [(case, activity, pd.Timestamp("2024-01-01") + pd.Timedelta(hours=i))
            for case, activities in traces.items() for i, activity in enumerate(activities)]
    return pd.DataFrame(rows, columns=["case_id", "activity", "timestamp"])


def test_vocabulary_check_reports_mismatch():
    events = make_events({"1": ["Order", "Leave"]})
    # Names from the original notebook's "ideal" model, which never occur in the log.
    result = vocabulary_check(events, ["Order", "Pharmacy Request Sent"])
    assert result == {"only_in_log": ["Leave"], "only_in_model": ["Pharmacy Request Sent"], "shared": ["Order"]}


@pytest.mark.pm4py
def test_sequential_net_structure():
    net, initial, final = build_sequential_net(["A", "B", "C"])
    assert model_activities(net) == {"A", "B", "C"}
    assert len(net.places) == 4 and len(net.arcs) == 6


def test_sequential_net_rejects_bad_input():
    with pytest.raises(ValueError):
        build_sequential_net([])
    with pytest.raises(ValueError):
        build_sequential_net(["A", "A"])


@pytest.mark.pm4py
def test_token_replay_distinguishes_fitting_and_deviating_cases():
    events = make_events({
        "fit": ["A", "B", "C"],
        "skip": ["A", "C"],      # B skipped
        "swap": ["B", "A", "C"],  # wrong order
    })
    net, initial, final = build_sequential_net(["A", "B", "C"])

    metrics, per_case = token_replay(events, net, initial, final)
    per_case = per_case.set_index("case_id")

    assert per_case.loc["fit", "is_fit"] and per_case.loc["fit", "fitness"] == 1.0
    assert not per_case.loc["skip", "is_fit"] and per_case.loc["skip", "fitness"] < 1.0
    assert not per_case.loc["swap", "is_fit"]
    assert metrics["perc_fit_traces"] == pytest.approx(100 / 3)


def test_check_precedence():
    events = make_events({
        "ok": ["Order", "Leave"],
        "missing": ["Leave"],
        "late": ["Leave", "Order"],
        "no_leave": ["Order"],
    })
    result = check_precedence(events, before="Order", after="Leave").set_index("case_id")

    assert result["violation"].to_dict() == {"late": True, "missing": True, "ok": False}
