"""Process variant analysis.

A *variant* is a distinct sequence of activities. Cases with exactly the
same sequence share a variant. Counting variants shows how standardised a
process is: a few dominant variants suggest a stable path, and a long tail
of rare variants suggests workarounds or data-quality problems.

This is computed with plain pandas instead of PM4Py. The original notebook
broke on a PM4Py API change (``get_variant_statistics`` does not exist), and
``pm4py.get_variants`` has changed its return type between versions. A
groupby is version-independent and easy to verify by hand.

Input: prepared events (see ``data_preparation``), already ordered within
each case.
"""

import pandas as pd

from . import config


def case_sequences(events: pd.DataFrame) -> pd.Series:
    """Return each case's activity sequence as a tuple, indexed by case ID.

    The order of the rows in ``events`` is used as-is, so pass events that
    were prepared with the intended ordering.
    """
    return events.groupby(config.CASE_COL, sort=True)[config.ACTIVITY_COL].agg(tuple)


def variant_table(events: pd.DataFrame) -> pd.DataFrame:
    """Count cases per variant.

    Args:
        events: Prepared events, ordered within each case.

    Returns:
        One row per variant, most frequent first, with the columns:
        ``variant_id`` (1 = most frequent), ``activities`` (tuple),
        ``n_activities``, ``case_count``, ``case_pct`` (percentage of all
        cases) and ``cumulative_pct``. Ties in frequency are ordered by the
        activity sequence, so the ranking is reproducible.
        An empty input gives an empty table with the same columns.
    """
    columns = ["variant_id", "activities", "n_activities", "case_count", "case_pct", "cumulative_pct"]
    sequences = case_sequences(events)
    if sequences.empty:
        return pd.DataFrame(columns=columns)

    table = sequences.value_counts().rename_axis("activities").reset_index(name="case_count")
    table["sort_key"] = table["activities"].map(" > ".join)
    table = table.sort_values(["case_count", "sort_key"], ascending=[False, True]).reset_index(drop=True)

    total_cases = table["case_count"].sum()
    table["variant_id"] = range(1, len(table) + 1)
    table["n_activities"] = table["activities"].map(len)
    table["case_pct"] = 100 * table["case_count"] / total_cases
    table["cumulative_pct"] = table["case_pct"].cumsum()
    return table[columns]


def variant_summary(table: pd.DataFrame, rare_max_cases: int = 1) -> dict[str, float]:
    """Summarise a variant table in a few headline numbers.

    Args:
        table: Output of :func:`variant_table`.
        rare_max_cases: Variants with at most this many cases count as rare.

    Returns:
        A dict with ``n_cases``, ``n_variants``, ``top_variant_pct``,
        ``top10_pct`` (share of cases covered by the 10 most frequent
        variants), ``n_rare_variants`` and ``rare_case_pct``.
    """
    if table.empty:
        return {"n_cases": 0, "n_variants": 0, "top_variant_pct": 0.0,
                "top10_pct": 0.0, "n_rare_variants": 0, "rare_case_pct": 0.0}
    rare = table["case_count"] <= rare_max_cases
    return {
        "n_cases": int(table["case_count"].sum()),
        "n_variants": len(table),
        "top_variant_pct": float(table["case_pct"].iloc[0]),
        "top10_pct": float(table["case_pct"].head(10).sum()),
        "n_rare_variants": int(rare.sum()),
        "rare_case_pct": float(table.loc[rare, "case_pct"].sum()),
    }


def format_variant(activities: tuple[str, ...], max_length: int = 0) -> str:
    """Join an activity sequence into a readable "A > B > C" label.

    Args:
        activities: The variant's activity sequence.
        max_length: If positive, truncate the label to this many characters.
    """
    label = " > ".join(activities)
    if max_length and len(label) > max_length:
        return label[: max_length - 3] + "..."
    return label
