# Findings and Limitations

This document separates what can be stated from what cannot. The original project material (notebook and presentation) is assessed in [audit_report.md](audit_report.md).

## A. Verified: about the original dataset (control flow only)

These facts come from recorded outputs of the original notebook run and from the surviving frequency DFG image. None of them depends on timestamps.

| Fact | Evidence |
|---|---|
| 13,710 event rows | Notebook cell 8 output (`Rows: 13710`). The activity counts in `original_frequency_dfg.png` sum to 13,710. |
| 2,500 cases | Notebook cell 12 (the notebook printed "Total events: 2500", but `len(EventLog)` counts cases) |
| 11 distinct activities | Notebook cell 30 |
| Near-linear path | `original_frequency_dfg.png`: apart from the main sequence, only three directly-follows edges appear, each with count 1 |
| Many cases cover only part of the process | Top-10 variants (cell 33) each start or end mid-process. Across 2,500 cases there are only 408 "Discharge Intent Documented" events and 421 "Patient Discharged (Left Facility)" events. |

**Caveat:** these results reflect the *row order* of the source file, because PM4Py kept file order. They are valid only if that file was written in true event order. This cannot be checked because the file is gone.

**Observation about the data's origin:** every one of the top-10 variants is a contiguous slice of one fixed 11-step sequence, with no loops, skipped steps or repeats, and the variant frequencies are very even (76 to 108 cases). This pattern is typical of generated data. The dataset's source was never documented, so it should not be presented as real hospital data.

## B. Verified: about this code (on synthetic data)

From `pytest` (70 tests) and a pipeline run on `data/sample/synthetic_discharge_events.csv`:

- All injected data-quality problems are detected with exact counts. Loaded 5,243 rows, rejected 8 (3 missing timestamps, 2 invalid timestamps, 2 missing activities, 1 missing case ID), retained 5,235. The 4 exact duplicates are flagged.
- Sorting by timestamp gives zero negative durations on consistent timestamps.
- The slowest-transition ranking recovers the generator's designed order (Transport 2.52 h, Medication Prepared 1.60 h, Physician Signature 1.03 h, against designed medians of 2.5 h, 1.5 h and 1.0 h).

These numbers describe the synthetic data. **They are not hospital findings.**

## C. Cannot be established from the available data

| Claim (source) | Why it cannot be established |
|---|---|
| Any case duration, waiting time or bottleneck from the original notebook (e.g. "slowest transition ≈ 252 hours", "average case duration −48,477 s") | Timestamps were random (see section D) |
| "10,000 discharge cases over 6 months" (slide 5) | The notebook's data had 2,500 cases. The data source is listed as "[EHR System Name]". |
| "Only 12% of cases follow the official SOP" (slide 8) | No SOP model exists in the project; no code computes this |
| "Median 3.1 h pharmacist wait", "50% longer on weekends" (slide 9) | No pharmacist-review activity and no resource or shift data in the log; times were random |
| "15% / 35% of cases loop back to physician signature" (slides 9, 15) | The original DFG shows no such loop (at most single cases deviate) |
| "Average wait 90 minutes for pharmacy", "15% missing follow-up" (slide 15) | No follow-up activity exists in the log; times were random |
| "8.5 h → 6.4 h LOS", "15 beds/day", "10% fewer readmissions", ROI (slides 2, 20, 21) | Slide 2 labels 8.5 h as a *hypothetical case*. No code, cost or readmission data supports these figures. |
| "Model fitness 1.00" / "represents the real log accurately" (notebook report) | Circular: the model was discovered from, and replayed on, the same 108 cases of one variant |
| "Alignment-based conformance checking" (notebook report) | Token-based replay was actually used |

The presentation's improvement ideas (start pharmacy preparation on the preliminary order, EHR checklists and hard-stops, standardised hand-offs) are reasonable **proposals**. They remain proposals until they are tested on real data.

## D. The negative-duration issue

1. The original notebook replaced the `Timestamp` column with independent random values between 2025-10-01 and 2025-11-30 (`random.randint`, no seed), so every run produced different times.
2. The final CSV was saved unsorted (cell 4 overwrote the earlier sorted versions).
3. PM4Py kept file order within each case, and `get_all_case_durations` computes "last minus first". Whenever the last row's random time was earlier than the first row's, the duration was negative: average **−48,477 s**, minimum **−4,258,234 s** (about −49 days).
4. Sorting by timestamp would have removed the negative values **without making the durations meaningful**, and would also have scrambled the activity order. The correct handling is to mark these timestamps as `unreliable` and not report timing results.

Notebook section 8 reproduces mechanism (3) with three events, and `tests/test_performance_analysis.py::test_file_order_reproduces_original_negative_duration` locks it in.

## E. Remaining limitations

- **No real data.** All runnable results use synthetic data.
- **One timestamp per event.** Activity processing times cannot be measured; transition gaps mix waiting and work.
- **No independent reference model.** Conformance measures similarity to the dominant path, not compliance. The original "TO-BE" Petri net (notebook cells 70/71, never run successfully) is also not a valid reference. Its place `prelim_order_written` feeds two transitions, which models an exclusive *choice* rather than parallel work, and its pharmacy branch ends in a dead-end place, so the net is not a sound workflow net. Its activity names also do not occur in the log.
- **No resource, ward or patient attributes**, so staffing or patient-mix effects cannot be analysed.
- **Timezone:** source timestamps carry no timezone and are treated as local clock time. Daylight-saving transitions could distort gaps of about one hour.
- **Rejected rows create artificial transitions.** Removing an event joins its neighbours. The impact is limited by ranking only transitions seen ≥ 10 times, and rejected rows are listed in full.
- **Tested environment:** Python 3.14.6 on Windows 11 with the versions in `requirements.txt`. The CI workflow (Python 3.12 and 3.14 on Ubuntu) has not been run yet.
- **Graphviz** is not required for any core output. The optional PM4Py diagram functions (`save_dfg_diagram`, `save_petri_net_diagram`) were not run, because Graphviz is not installed on the development machine.
