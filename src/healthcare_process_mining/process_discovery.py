"""Control-flow discovery: which activities happen, in what order.

This module answers "what does the process look like?" without using any
durations, so its results stay valid even when timestamps are not
trustworthy, provided the event *order* is.

* The Directly-Follows Graph (DFG) and activity frequencies are computed with
  pandas. They are simple counts, easy to test, and independent of PM4Py
  version changes.
* Petri-net discovery (Inductive or Heuristics Miner) uses PM4Py's stable
  top-level API (``pm4py.discover_petri_net_*``).

Ordering guarantee: :func:`build_event_log` hands PM4Py events in exactly the
order produced by ``data_preparation``. PM4Py's ``convert_to_event_log``
keeps row order and does NOT re-sort by timestamp (verified for PM4Py
2.7.23 in ``tests/test_process_discovery.py``). Forgetting this is how the
original notebook ended up with negative case durations.
"""

import pandas as pd

from . import config

# PM4Py's standard (XES) attribute names.
PM4PY_CASE = "case:concept:name"
PM4PY_ACTIVITY = "concept:name"
PM4PY_TIMESTAMP = "time:timestamp"


def activity_frequency(events: pd.DataFrame) -> pd.DataFrame:
    """Count events and cases per activity.

    Returns:
        One row per activity with ``event_count`` (all occurrences) and
        ``case_count`` (cases containing it at least once), sorted by
        event count descending. The two differ when activities repeat
        within a case (rework).
    """
    grouped = events.groupby(config.ACTIVITY_COL)
    table = pd.DataFrame({
        "event_count": grouped.size(),
        "case_count": grouped[config.CASE_COL].nunique(),
    })
    return table.sort_values(["event_count"], ascending=False).rename_axis("activity").reset_index()


def compute_dfg(events: pd.DataFrame) -> pd.DataFrame:
    """Count how often each activity is directly followed by another, within a case.

    Args:
        events: Prepared events, ordered within each case.

    Returns:
        A table with ``source``, ``target`` and ``count``, most frequent first.
    """
    next_activity = events.groupby(config.CASE_COL)[config.ACTIVITY_COL].shift(-1)
    pairs = pd.DataFrame({"source": events[config.ACTIVITY_COL], "target": next_activity}).dropna()
    if pairs.empty:
        return pd.DataFrame(columns=["source", "target", "count"])
    return (pairs.value_counts().rename("count").reset_index()
            .sort_values(["count", "source", "target"], ascending=[False, True, True])
            .reset_index(drop=True))


def start_end_activities(events: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Count the first and the last activity of every case.

    Returns:
        Two Series (start counts, end counts), indexed by activity name.
    """
    grouped = events.groupby(config.CASE_COL)[config.ACTIVITY_COL]
    return grouped.first().value_counts(), grouped.last().value_counts()


def build_event_log(events: pd.DataFrame):
    """Convert prepared events into a PM4Py ``EventLog``, preserving their order.

    Args:
        events: Prepared events from ``data_preparation``.

    Returns:
        A ``pm4py.objects.log.obj.EventLog`` with one trace per case.
    """
    import pm4py  # imported here so the pandas-only modules work without PM4Py

    renamed = events.rename(columns={
        config.CASE_COL: PM4PY_CASE,
        config.ACTIVITY_COL: PM4PY_ACTIVITY,
        config.TIMESTAMP_COL: PM4PY_TIMESTAMP,
    })
    # PM4Py expects plain Python strings rather than pandas' string dtype.
    renamed[PM4PY_CASE] = renamed[PM4PY_CASE].astype(object)
    renamed[PM4PY_ACTIVITY] = renamed[PM4PY_ACTIVITY].astype(object)
    return pm4py.convert_to_event_log(renamed, case_id_key=PM4PY_CASE)


def discover_petri_net(events: pd.DataFrame, algorithm: str = "inductive", noise_threshold: float = 0.0):
    """Discover a Petri net that describes the observed behaviour.

    A discovered model describes what *happened*. It is not a reference model
    of what *should* happen; see ``conformance_checking``.

    Args:
        events: Prepared events, ordered within each case.
        algorithm: ``"inductive"`` (guarantees a sound model that can replay
            every trace when ``noise_threshold`` is 0) or ``"heuristics"``
            (tolerates noise; used in the original notebook and presentation).
        noise_threshold: Inductive Miner only. Between 0 and 1; higher values
            ignore infrequent behaviour.

    Returns:
        ``(net, initial_marking, final_marking)``.

    Raises:
        ValueError: If ``algorithm`` is not recognised or ``events`` is empty.
    """
    if algorithm not in ("inductive", "heuristics"):
        raise ValueError(f"Unknown algorithm '{algorithm}'. Use 'inductive' or 'heuristics'.")
    if events.empty:
        raise ValueError("Cannot discover a model from an empty event log.")

    import pm4py

    log = build_event_log(events)
    if algorithm == "inductive":
        return pm4py.discover_petri_net_inductive(log, noise_threshold=noise_threshold)
    return pm4py.discover_petri_net_heuristics(log)
