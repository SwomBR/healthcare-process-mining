"""Shared configuration for the healthcare process mining project.

This module keeps column names, file locations and the activity vocabulary
in one place so the other modules do not hardcode them. Nothing here reads
files or changes state; it only defines constants.
"""

from pathlib import Path

# --- Paths -------------------------------------------------------------------
# PROJECT_ROOT is derived from this file's location (src/healthcare_process_mining/),
# so the project works from any folder on any computer.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
SAMPLE_DATA_DIR = DATA_DIR / "sample"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

SYNTHETIC_SAMPLE_FILE = SAMPLE_DATA_DIR / "synthetic_discharge_events.csv"

# --- Column names ------------------------------------------------------------
# The modules work with short, simple internal column names.
CASE_COL = "case_id"
ACTIVITY_COL = "activity"
TIMESTAMP_COL = "timestamp"
# Position of each row in the source file. Kept so every prepared or rejected
# event can be traced back to the original record.
SOURCE_ROW_COL = "source_row"

# Column names used by the original capstone CSV, mapped to the internal names.
SOURCE_COLUMN_MAP = {
    "Case ID": CASE_COL,
    "Activity": ACTIVITY_COL,
    "Timestamp": TIMESTAMP_COL,
}

REQUIRED_COLUMNS = [CASE_COL, ACTIVITY_COL, TIMESTAMP_COL]

# Format the original notebook used when writing the CSV
# (to_csv(..., date_format="%Y-%m-%d %H:%M:%S")). An explicit format is
# safer than letting pandas guess, which can confuse day and month.
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# --- Activity vocabulary -----------------------------------------------------
# The 11 activities found in the original dataset (notebook output, cell 30),
# listed in the order in which they appear in the original frequency DFG
# (outputs/figures/original_frequency_dfg.png).
#
# IMPORTANT: this order was observed in the data. It is NOT an official hospital
# SOP. Conformance results against it measure "agreement with the dominant
# observed path", not regulatory compliance.
EXPECTED_ACTIVITIES = [
    "Discharge Intent Documented",
    "Med Reconciliation Completed",
    "Discharge Order Written",
    "Medication Prepared",
    "Nursing Notified for Discharge",
    "Physician Final Signature",
    "Discharge Education Provided",
    "Patient Billing Cleared",
    "Discharge Summary Completed",
    "Patient Transport Arranged",
    "Patient Discharged (Left Facility)",
]

# --- Timestamp provenance ----------------------------------------------------
# Performance analysis is only meaningful when the timestamps describe when
# events really happened. The pipeline therefore asks where they came from.
TIMESTAMP_PROVENANCE_OPTIONS = {
    "original": "Recorded by the source system; performance results are findings.",
    "synthetic": "Generated for demonstration; performance results are illustrative only.",
    "unreliable": "Known to be wrong (e.g. randomly assigned); performance analysis is skipped.",
}

# --- Analysis settings -------------------------------------------------------
LONG_RUNNING_QUANTILE = 0.90  # cases above this duration quantile are "long-running"
TOP_N = 10  # rows shown in "top N" tables and charts
# Transitions seen fewer times than this are left out of "slowest transition"
# rankings (they stay in the full CSV). A median of one or two observations is
# not evidence of a bottleneck, and rare transitions are often artefacts: a
# rejected row joins its neighbours into a transition that never happened.
MIN_TRANSITION_COUNT = 10
