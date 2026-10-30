# Data Dictionary

## Input columns

The original dataset had exactly these three columns (notebook output: `Initial columns: ['Case ID', 'Activity', 'Timestamp']`). No other attributes such as ward, resource or patient details were present, so none are documented here.

| Source column | Internal name | Type after preparation | Definition | Validation rule |
|---|---|---|---|---|
| `Case ID` | `case_id` | string | Identifier of one discharge encounter. Original values looked like `Encounter_102019`; synthetic values look like `SYN-00001`. | Required. Blank or whitespace-only values are rejected (`missing_case_id`). |
| `Activity` | `activity` | string | Name of the recorded discharge step. | Required (`missing_activity`). Names outside the 11 known activities are reported (`unexpected_activity`), not removed. |
| `Timestamp` | `timestamp` | datetime (naive) | When the step was recorded. Format `YYYY-MM-DD HH:MM:SS`. No timezone in the source, so values are treated as local clock time. | Missing (`missing_timestamp`) and unparseable (`invalid_timestamp`) values are counted separately and rejected when ordering by timestamp. Never filled in. |

## Columns added by preparation

| Column | Meaning |
|---|---|
| `source_row` | Zero-based row number in the input file. Lets every event be traced back to the source. |
| `rejection_reason` | (rejected rows only) The first rule the row failed. |
| `timestamp_as_recorded` | (rejected rows only) The original timestamp text, before parsing. |

## Activity vocabulary

These are the 11 activities observed in the original data (notebook cell 30), in the order of the dominant path in the original frequency DFG. Event counts are read from `outputs/figures/original_frequency_dfg.png`, the only surviving output of the original run that does not depend on timestamps. The counts sum to 13,710, matching the original row count.

| # | Activity | Events in original data |
|---|---|---|
| 1 | Discharge Intent Documented | 408 |
| 2 | Med Reconciliation Completed | 816 |
| 3 | Discharge Order Written | 1,239 |
| 4 | Medication Prepared | 1,601 |
| 5 | Nursing Notified for Discharge | 1,797 |
| 6 | Physician Final Signature | 1,863 |
| 7 | Discharge Education Provided | 1,828 |
| 8 | Patient Billing Cleared | 1,644 |
| 9 | Discharge Summary Completed | 1,253 |
| 10 | Patient Transport Arranged | 840 |
| 11 | Patient Discharged (Left Facility) | 421 |

The meaning of each activity is taken from its name only. No source system documentation was available, so no further definitions are given.

## Data-quality checks

All checks are in `data_validation.py`. Each check reports a count, the rule and the handling.

| Check | Unit | Handling |
|---|---|---|
| `missing_case_id` | rows | Rejected |
| `missing_activity` | rows | Rejected |
| `missing_timestamp` | rows | Rejected when ordering by timestamp |
| `invalid_timestamp` | rows | Rejected when ordering by timestamp |
| `exact_duplicate` (same case, activity *and* timestamp) | rows | Flagged and kept; `--drop-duplicates` removes them. A repeated activity at a *different* time is treated as rework, not as a duplicate. |
| `same_timestamp_in_case` | rows | Kept; ties keep source-file order |
| `case_order_conflict` (rows of a case go backwards in time in the file) | cases | Kept; events are re-sorted by timestamp |
| `single_event_case` | cases | Kept; excluded from duration statistics |
| `unexpected_activity` | rows | Kept and listed |
