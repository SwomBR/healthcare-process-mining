# Project Overview

## Business problem

Hospital discharge is a multi-team process involving physicians, nursing, pharmacy, billing and transport. Delays at discharge keep beds occupied and push back new admissions. Official procedures describe how discharge *should* run. Process mining reconstructs how it *actually* runs, from the timestamps that hospital systems record for each step.

## Origin

This began as a group capstone project (four members) titled *"Using Process Mining Algorithms for Process Improvement in Healthcare"*. The original work was a Google Colab notebook and a 24-slide presentation. This repository is a refactored, tested and documented version of the analysis code. The audit of the original material is in [audit_report.md](audit_report.md).

## Scope

- **Process:** patient discharge, from "Discharge Intent Documented" to "Patient Discharged (Left Facility)", with 11 activities.
- **Analyses:** data-quality validation, control-flow discovery (DFG, Petri nets), variant analysis, performance analysis (case durations and gaps between steps) and conformance checking.
- **Out of scope:** resource and staffing analysis (the data has no resource column), activity processing times (only one timestamp per event), and cost or ROI estimates (no cost data).

## Inputs

An event log in CSV format with one row per recorded step: `Case ID`, `Activity`, `Timestamp`. See [data_dictionary.md](data_dictionary.md).

- The original dataset is **not available** (see [findings_and_limitations.md](findings_and_limitations.md)).
- A synthetic sample with known properties is included for demonstration.

## Outputs

Running `python -m healthcare_process_mining --timestamps synthetic` writes:

| Output | Location |
|---|---|
| Markdown analysis report | `outputs/reports/analysis_report.md` |
| Data-quality check table, rejected records with reasons | `outputs/reports/data_quality_checks.csv`, `rejected_records.csv` |
| Activity frequency, directly-follows counts, variants | `outputs/reports/*.csv` |
| Case durations, transition-gap summary (if timestamps allow) | `outputs/reports/*.csv` |
| Per-case conformance results | `outputs/reports/conformance_per_case.csv` |
| Charts | `outputs/figures/*.png` |

## Objectives

1. Make data-quality problems visible and countable before any analysis.
2. Describe the process structure: its main path, its variation, and its deviations.
3. Measure time between steps **only when the timestamps support it**, and label results by where the timestamps came from.
4. Compare cases with a reference process, stating clearly what that reference is and is not.
5. Keep every reported number traceable to code and covered by tests.
