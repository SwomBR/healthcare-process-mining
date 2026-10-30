"""Generate a SYNTHETIC discharge event log for demonstration and testing.

The original capstone dataset is not available, and its timestamps were
randomly assigned anyway. This module creates a small, fully synthetic log
so the whole pipeline can be run end to end without any patient data.

Everything here is invented: case IDs, timings and process variations.
Results computed from this data demonstrate that the *code* works. They
say nothing about any real hospital.

Because the generating rules are known (see ``TRANSITION_MEDIAN_MINUTES``
and the probabilities below), the synthetic log doubles as a correctness
check: the analysis should recover the rules that were put in, such as the
longest median gap.

Run as a script to (re)create ``data/sample/synthetic_discharge_events.csv``::

    python -m healthcare_process_mining.synthetic_data
"""

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

# Invented median gap (in minutes) before each activity, i.e. from the
# previous event to this one. "Patient Transport Arranged" is deliberately
# the slowest so tests can confirm it is detected as the largest median gap.
TRANSITION_MEDIAN_MINUTES = {
    "Discharge Intent Documented": 0,
    "Med Reconciliation Completed": 45,
    "Discharge Order Written": 30,
    "Medication Prepared": 90,
    "Nursing Notified for Discharge": 20,
    "Physician Final Signature": 60,
    "Discharge Education Provided": 40,
    "Patient Billing Cleared": 35,
    "Discharge Summary Completed": 50,
    "Patient Transport Arranged": 150,
    "Patient Discharged (Left Facility)": 30,
}

P_SKIP_INTENT = 0.30  # "Discharge Intent Documented" not recorded
P_SKIP_MED_REC = 0.10  # "Med Reconciliation Completed" not recorded
P_SWAP_EDUCATION_BILLING = 0.20  # billing cleared before education
P_REWORK_SIGNATURE = 0.12  # summary sent back for a second physician signature
P_INCOMPLETE = 0.05  # case still open when the log was extracted

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _case_path(rng: np.random.Generator) -> list[str]:
    """Draw one case's activity sequence from the invented process rules."""
    path = list(config.EXPECTED_ACTIVITIES)
    if rng.random() < P_SKIP_INTENT:
        path.remove("Discharge Intent Documented")
    if rng.random() < P_SKIP_MED_REC:
        path.remove("Med Reconciliation Completed")
    if rng.random() < P_SWAP_EDUCATION_BILLING:
        i, j = path.index("Discharge Education Provided"), path.index("Patient Billing Cleared")
        path[i], path[j] = path[j], path[i]
    if rng.random() < P_REWORK_SIGNATURE:
        k = path.index("Discharge Summary Completed") + 1
        path[k:k] = ["Physician Final Signature", "Discharge Summary Completed"]
    if rng.random() < P_INCOMPLETE:
        path = path[: rng.integers(2, len(path))]
    return path


def generate_clean_log(n_cases: int = 500, seed: int = 42) -> pd.DataFrame:
    """Generate a synthetic event log without any data-quality problems.

    Args:
        n_cases: Number of discharge cases to simulate.
        seed: Random seed. The same seed always gives the same log.

    Returns:
        A DataFrame with the original dataset's column names
        (``Case ID``, ``Activity``, ``Timestamp``), sorted by case and time.
    """
    rng = np.random.default_rng(seed)
    period_start = datetime(2024, 1, 1)
    rows = []
    for case_number in range(1, n_cases + 1):
        # Cases start on a random day in Q1 2024, between 08:00 and 14:00.
        time = period_start + timedelta(days=int(rng.integers(0, 90)), minutes=int(rng.integers(8 * 60, 14 * 60)))
        for position, activity in enumerate(_case_path(rng)):
            if position > 0:
                median = TRANSITION_MEDIAN_MINUTES[activity]
                # Log-normal gaps: always positive and right-skewed, like real waits.
                minutes = max(1.0, rng.lognormal(mean=np.log(median), sigma=0.5))
                time = time + timedelta(minutes=round(minutes))
            rows.append({"Case ID": f"SYN-{case_number:05d}", "Activity": activity,
                         "Timestamp": time.strftime(TIMESTAMP_FORMAT)})
    return pd.DataFrame(rows)


def inject_quality_issues(clean: pd.DataFrame, seed: int = 42) -> tuple[pd.DataFrame, dict[str, int]]:
    """Add a known number of typical data-quality problems to a clean log.

    The problems mirror what real extracts contain (and what the validation
    module must catch): missing values, unparseable timestamps, double
    recordings and a file that is not in chronological order.

    Args:
        clean: Output of :func:`generate_clean_log`.
        seed: Random seed for choosing the affected rows.

    Returns:
        The modified log, and a dict with the exact number of rows affected
        by each injected problem (useful as ground truth in tests).
    """
    rng = np.random.default_rng(seed)
    df = clean.copy()
    # Choose distinct rows for each problem so the counts stay exact.
    chosen = rng.choice(len(df), size=8, replace=False)
    missing_ts, invalid_ts, missing_act, missing_case = chosen[:3], chosen[3:5], chosen[5:7], chosen[7:]
    df.loc[missing_ts, "Timestamp"] = np.nan
    df.loc[invalid_ts, "Timestamp"] = ["2024-13-45 10:00:00", "not recorded"]
    df.loc[missing_act, "Activity"] = np.nan
    df.loc[missing_case, "Case ID"] = np.nan

    untouched = np.setdiff1d(np.arange(len(df)), chosen)
    duplicates = df.loc[rng.choice(untouched, size=4, replace=False)]
    df = pd.concat([df, duplicates], ignore_index=True)

    # Shuffle the file so rows are no longer in time order (as in the original
    # CSV). Correct analysis must sort by timestamp rather than trust file order.
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)

    injected = {"missing_timestamp": 3, "invalid_timestamp": 2, "missing_activity": 2,
                "missing_case_id": 1, "exact_duplicate": 4}
    return df, injected


def write_sample_file(path: Path = config.SYNTHETIC_SAMPLE_FILE, n_cases: int = 500, seed: int = 42) -> Path:
    """Generate the synthetic log with injected issues and save it as CSV.

    Returns:
        The path that was written.
    """
    data, _ = inject_quality_issues(generate_clean_log(n_cases, seed), seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(path, index=False)
    return path


if __name__ == "__main__":
    print(f"Wrote synthetic sample data to {write_sample_file()}")
