"""Shared test fixtures: tiny, hand-checkable event logs.

Every fixture is small enough that the expected results can be worked out
on paper, which is what makes the assertions in the tests trustworthy.
"""

import pandas as pd
import pytest


@pytest.fixture
def raw_log() -> pd.DataFrame:
    """Raw log using the original CSV's column names, deliberately NOT in time order.

    Case A: Order 08:00 -> Med 10:00 -> Leave 13:00 (rows 0-2 are written out of order)
    Case B: Order 09:00 -> Leave 09:30
    Case C: a single event
    """
    return pd.DataFrame({
        "Case ID": ["A", "A", "A", "B", "B", "C"],
        "Activity": ["Leave", "Order", "Med", "Order", "Leave", "Order"],
        "Timestamp": [
            "2024-01-01 13:00:00",
            "2024-01-01 08:00:00",
            "2024-01-01 10:00:00",
            "2024-01-02 09:00:00",
            "2024-01-02 09:30:00",
            "2024-01-03 12:00:00",
        ],
    })


@pytest.fixture
def standardized_log(raw_log: pd.DataFrame) -> pd.DataFrame:
    """The raw log with internal column names, timestamps still as text."""
    return raw_log.rename(columns={"Case ID": "case_id", "Activity": "activity", "Timestamp": "timestamp"})
