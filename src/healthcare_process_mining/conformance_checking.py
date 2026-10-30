"""Conformance checking: compare observed behaviour with a reference model.

Conformance checking answers "do cases follow the intended process?". The
answer is only as meaningful as the reference model:

* A model **discovered from the same log** will fit that log by construction.
  In the original notebook, a model discovered from the 108 cases of the most
  frequent variant was replayed on those same 108 cases, so a fitness of 1.00
  was guaranteed. That is not evidence of compliance.
* A real compliance statement needs an **independent** reference model, such
  as an approved SOP. The project does not have one. The presentation's
  "7-step High-Risk Discharge Protocol" was never provided as data.
* The reference used in the demonstration is the activity order in
  ``config.EXPECTED_ACTIVITIES``. It comes from the original data's dominant
  path, so results mean "agreement with the usual path", not "compliance".

Before replaying, :func:`vocabulary_check` confirms that the model and the
log use the same activity names. The original notebook's "ideal" model used
names such as "Pharmacy Request Sent" that never occur in the log, so it
could never have fitted.
"""

import pandas as pd

from . import config
from .process_discovery import build_event_log


def build_sequential_net(activities: list[str], name: str = "reference_process"):
    """Build a Petri net in which the given activities must occur in that order, once each.

    This is the same construction as the original notebook's hand-built
    "ideal" model, written as a loop instead of repeated lines.

    Args:
        activities: Activity names in the required order.
        name: Name for the net.

    Returns:
        ``(net, initial_marking, final_marking)``.

    Raises:
        ValueError: If ``activities`` is empty or contains duplicates.
    """
    if not activities:
        raise ValueError("A reference model needs at least one activity.")
    if len(set(activities)) != len(activities):
        raise ValueError("Activities must be unique in a sequential model.")

    from pm4py.objects.petri_net.obj import Marking, PetriNet
    from pm4py.objects.petri_net.utils import petri_utils

    net = PetriNet(name)
    # A sequence of n activities needs n + 1 places: p0 -> t1 -> p1 -> ... -> pn.
    places = [PetriNet.Place(f"p{i}") for i in range(len(activities) + 1)]
    for place in places:
        net.places.add(place)
    for i, activity in enumerate(activities):
        transition = PetriNet.Transition(f"t{i}", activity)
        net.transitions.add(transition)
        petri_utils.add_arc_from_to(places[i], transition, net)
        petri_utils.add_arc_from_to(transition, places[i + 1], net)

    initial, final = Marking(), Marking()
    initial[places[0]] = 1
    final[places[-1]] = 1
    return net, initial, final


def model_activities(net) -> set[str]:
    """Return the visible activity labels of a Petri net (silent steps excluded)."""
    return {transition.label for transition in net.transitions if transition.label is not None}


def vocabulary_check(events: pd.DataFrame, reference_activities: set[str] | list[str]) -> dict[str, list[str]]:
    """Compare the activity names in the log with those in a reference model.

    Returns:
        A dict with ``only_in_log``, ``only_in_model`` and ``shared`` (sorted
        lists). If ``shared`` is empty, conformance results are meaningless.
    """
    in_log = set(events[config.ACTIVITY_COL].dropna().unique())
    in_model = set(reference_activities)
    return {
        "only_in_log": sorted(in_log - in_model),
        "only_in_model": sorted(in_model - in_log),
        "shared": sorted(in_log & in_model),
    }


def token_replay(events: pd.DataFrame, net, initial_marking, final_marking) -> tuple[dict[str, float], pd.DataFrame]:
    """Replay every case on a Petri net with token-based replay.

    Token-based replay "plays" each case on the model and counts tokens that
    had to be added (missing: a step happened without its prerequisite) or
    were left over (remaining: a required step never happened).

    Args:
        events: Prepared events, ordered within each case.
        net, initial_marking, final_marking: The reference model.

    Returns:
        A tuple of:

        * log-level metrics from ``pm4py.fitness_token_based_replay``:
          ``perc_fit_traces`` (percentage of cases replayed perfectly),
          ``average_trace_fitness`` and ``log_fitness`` (both 0 to 1);
        * a per-case DataFrame with ``case_id``, ``is_fit``, ``fitness``,
          ``missing_tokens`` and ``remaining_tokens``.
    """
    import pm4py

    log = build_event_log(events)
    metrics = pm4py.fitness_token_based_replay(log, net, initial_marking, final_marking)
    diagnostics = pm4py.conformance_diagnostics_token_based_replay(log, net, initial_marking, final_marking)
    per_case = pd.DataFrame({
        "case_id": [trace.attributes["concept:name"] for trace in log],
        "is_fit": [d["trace_is_fit"] for d in diagnostics],
        "fitness": [d["trace_fitness"] for d in diagnostics],
        "missing_tokens": [d["missing_tokens"] for d in diagnostics],
        "remaining_tokens": [d["remaining_tokens"] for d in diagnostics],
    })
    return {key: float(value) for key, value in metrics.items()}, per_case


def check_precedence(events: pd.DataFrame, before: str, after: str) -> pd.DataFrame:
    """Check a simple rule: ``after`` must not happen unless ``before`` happened earlier.

    This is a transparent, assumption-light alternative to a full process
    model, useful when only a few business rules are known. No rule is
    assumed by the project; callers supply their own.

    Args:
        events: Prepared events, ordered within each case.
        before: Activity that must come first.
        after: Activity that requires ``before``.

    Returns:
        One row per case containing ``after``, with ``has_before_earlier``
        and ``violation`` (True when ``after`` occurred without a preceding
        ``before``).
    """
    position = events.groupby(config.CASE_COL).cumcount()
    activity = events[config.ACTIVITY_COL]
    first_before = position[activity == before].groupby(events[config.CASE_COL]).min()
    first_after = position[activity == after].groupby(events[config.CASE_COL]).min()

    result = pd.DataFrame({"first_after": first_after}).join(first_before.rename("first_before"))
    result["has_before_earlier"] = result["first_before"] < result["first_after"]
    result["violation"] = ~result["has_before_earlier"]
    return result.rename_axis("case_id").reset_index()[["case_id", "has_before_earlier", "violation"]]
