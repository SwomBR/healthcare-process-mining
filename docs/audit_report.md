# Project Audit Report

Audit date: 2026-10-31. Covers the project folder as it was before refactoring.

## 1. Existing structure

| Item | Size | What it actually is |
|---|---|---|
| `capstone.ipynb` | 0.56 MB | Colab notebook, 68 cells (cell 67 empty). |
| `capstone vscode.ipynb` | 0.59 MB | The same 67 cells **with identical source and identical outputs**, plus 7 extra cells (72 to 73 in the list below) added in VS Code. |
| `CAPSTONE.py` | 1.5 MB | **Not Python.** It is a "Save page as" HTML export of the Colab page (`<!DOCTYPE html>`, saved from colab.research.google.com). |
| `CAPSTONE_files/` | ~13 MB, 60 files | Browser assets for that HTML page (Google JS, CSS, Monaco editor, reCAPTCHA, analytics). |
| `PROCESS MINING CAPSTONE PROJECT.pptx` | 49.5 MB | 24-slide group presentation (four named members). 64 embedded images; the largest are ~3.4 MB PNGs. |
| `spaghetti.png` | 64 KB | DFG ("spaghetti") image. |
| Data files | none | `discharge_events.csv` is **not in the folder and not on this machine**. |
| Git | none | The folder is not a Git repository. |
| README, requirements, tests, docs | none | |

The extra VS Code cells are: `pip`/`apt-get` installs (failed on Windows), a hand-built "TO-BE" Petri net (failed: pm4py not installed), an AS-IS vs TO-BE comparison table with hardcoded values (failed: pandas not installed), and a Colab-only download cell (failed).

**Authoritative notebook:** `capstone vscode.ipynb` is a strict superset of `capstone.ipynb`. Every executed output of the analysis comes from the Colab run (pm4py 2.7.19, Python 3.12). The Colab notebook can be retired once the VS Code notebook is kept.

## 2. What already works (in the recorded Colab run)

- The CSV loads into pandas and is renamed to PM4Py's standard columns.
- Conversion to a PM4Py event log works.
- A frequency DFG, a performance DFG, a Heuristics-net Petri net and an Inductive-Miner Petri net are discovered and drawn.
- Variants are listed using `pm4py.get_variants` (the fallback after the API error).
- Token-based replay runs.
- Histogram, top-variant and activity-frequency charts are produced.
- A text report and PDF reports (reportlab) are generated.

Recorded facts about the input that can be trusted, because they come from the notebook output: **13,710 rows**, columns `Case ID, Activity, Timestamp`, **2,500 cases**, and **11 distinct activities**.

## 3. What is incomplete or broken

- Cell 34 calls `get_variant_statistics`, which does not exist in `pm4py.statistics.variants.log.get`.
- Cell 19 replays the log against a hand-built "ideal" Petri net. The result is never evaluated. Its transitions (`Pharmacy Request Sent`, `Pharmacy Prep Start`, `Final Physician Sign-off`, `Patient Leaves Facility`, ...) **do not exist in the event log**, so the model could never fit.
- Cell 32 passes a 3-activity list to `paths_filter`, which expects (from, to) activity pairs. It reports "0 conforming / 2500 non-conforming", which is not a valid conformance result.
- The VS Code-only cells (TO-BE net and comparison table) never ran successfully.
- Many cells are duplicates: the timestamp generation appears 3 times, the Petri net twice, and token replay 5 times.
- Hardcoded Colab paths (`/content/...`), `google.colab` imports and `!pip install` cells mean the notebook does not run anywhere else.

## 4. Data-quality problems (critical)

1. **Every timestamp is artificial.** Cells 0, 2 and 4 replace the `Timestamp` column with `random.randint` values spread uniformly over 2025-10-01 to 2025-11-30, independently for every row and without a random seed. Any time-based metric therefore measures random noise and changes on every run.
2. **Root cause of the negative durations.** The final CSV was saved *unsorted* (cell 4 overwrote the sorted versions). PM4Py 2.7.19's `convert_to_event_log` kept the file's row order inside each case. `get_all_case_durations` computes "last event minus first event" in that order. With random timestamps, the last row is often earlier than the first, which gives the recorded average case duration of **-48,477 s** and a minimum of **-4,258,234 s**.
3. **Control-flow results depend on row order, not timestamps.** Variants and the frequency DFG reflect the original row order of `discharge_events.csv`. That is only meaningful if the source file was written in true event order, which is unverified.
4. **The source data looks synthetic.** Every one of the top-10 variants is a contiguous slice of one fixed 11-step sequence, with no loops, no repeats and no skipped steps. Variant counts are suspiciously uniform (76 to 108). The origin of `discharge_events.csv` is not documented anywhere.
5. Incomplete cases: many variants start or end mid-process (for example, they end at `Patient Billing Cleared`). It is unknown whether this is truncation of the log window or a real feature of the data.

## 5. Methodological problems

- **Mislabelled counts.** "Total events: 2500" is actually 2,500 *cases* (the length of a PM4Py EventLog is its number of traces). The report's "Total events: 108 / Total cases: 108" is 108 cases of one variant.
- **Circular conformance.** A model is discovered from the 108 cases of the single most frequent variant and replayed on those same 108 cases. A fitness of 1.00 is guaranteed and says nothing about compliance.
- **Wrong method named in the report.** The report says "alignment-based conformance checking", but token-based replay was used.
- **Unsupported conclusions.** The report states "The process model represents the real log accurately" and "bottlenecks identified". Neither follows from the computed results.
- **"Bottlenecks" are random gaps.** The slowest transitions (~10 to 13 days mean) are artefacts of the random timestamps.
- **The histogram mixes negative durations** in with the others without comment.
- **Hardcoded comparison values.** The AS-IS vs TO-BE table hardcodes "8.5 hours" and "Projected 6.4 hours". Slide 2 itself labels 8.5 h as a *hypothetical case*.
- **Presentation figures are not produced by any code:** 10,000 cases over 6 months, 12% SOP-compliant, 3.1 h median pharmacist wait, 15% / 35% rework loops, 90-minute pharmacy wait, 15% follow-up gaps, 2.1 h LOS reduction, 15 beds per day, 10% readmission reduction. The notebook's data has 2,500 cases and no loops at all. The "7-step High-Risk Discharge Protocol" reference model is not in the project. Slide 5 still contains the placeholder `[EHR System Name]`.

## 6. Duplicate or unnecessary files

- `capstone.ipynb`: redundant (a subset of the VS Code notebook). Proposed: remove from the published repo after you confirm.
- `CAPSTONE.py` + `CAPSTONE_files/`: a saved web page, not code. It holds Google tracking and editor scripts and no unique analysis. Proposed: exclude from the repo after you confirm.
- `PROCESS MINING CAPSTONE PROJECT.pptx` (49.5 MB): too large to clone comfortably, and it names group members. Proposed: keep it locally and publish a compressed PDF export or a link instead (your decision).
- Generated files referenced by the notebook (`bottlenecks.csv`, `process_mining_report.txt`, `*.pdf`) are not present. They should be regenerated by the pipeline, not committed by hand.

## 7. Recommended refactoring plan

1. Create the `src/healthcare_process_mining/` package: loader, validation, preparation, discovery, performance, variants, conformance, visualization, reporting and config.
2. Compute variants, case durations and transition gaps in plain pandas, so they are easy to test, version-independent and transparent. Use PM4Py for model discovery, DFG visualisation and replay through its stable top-level API (`pm4py.discover_*`, `pm4py.fitness_token_based_replay`).
3. Add a **timestamp-provenance gate**. Performance analysis runs only when the timestamps are declared original. Otherwise it is reported as "not established".
4. Never regenerate timestamps. Keep the random-timestamp step only as documented history in `docs/findings_and_limitations.md`.
5. Conformance: keep the hand-built TO-BE net as a *proposal*. Check it only against a log whose activity names match, and report the vocabulary mismatch explicitly. Do not present self-discovered-model fitness as compliance.
6. Provide a clearly labelled synthetic demo dataset with a seeded generator, so the full pipeline runs end to end without private data.
7. Add pytest tests on small in-test DataFrames, a CI workflow, a requirements file, a .gitignore and the docs.
8. Write one clean notebook that calls the package. Archive the original notebook unchanged under `notebooks/archive/` for traceability.
