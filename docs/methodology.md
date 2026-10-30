# Methodology

## 1. Event log

An event log is a table in which each row records that an **activity** happened in a **case** at a **time**. Grouping the rows by case and ordering them gives each case's *trace*: the sequence of steps it went through. Every analysis below depends on that ordering being correct.

**Ordering rule** (`data_preparation.prepare_event_log`):

- `order_by="timestamp"` (default): sort by case, then timestamp. Events with identical timestamps keep their source-file order, which makes the result reproducible.
- `order_by="file_order"`: keep the source row order. Use this only when the timestamps are known to be wrong *and* the file is believed to be in event order. Timing analysis is then switched off.

> **Why this matters.** PM4Py's `convert_to_event_log` keeps the row order it is given and does not sort by timestamp. This was verified for PM4Py 2.7.23.11 in `tests/test_process_discovery.py::test_event_log_preserves_prepared_order`, and the original notebook shows the same behaviour in 2.7.19. Ordering is therefore our responsibility, not the library's.

## 2. Timestamp provenance

The pipeline requires a `timestamp_provenance` value:

| Value | Meaning | Timing analysis |
|---|---|---|
| `original` | Times recorded by the source system | Computed and reported as findings |
| `synthetic` | Generated for demonstration | Computed and labelled "illustrative only" |
| `unreliable` | Known to be wrong (e.g. randomly assigned) | Skipped; the report says "Not established" |

This replaces the original notebook's implicit assumption that any timestamp accepted by PM4Py is meaningful.

## 3. Process discovery

- **Activity frequency:** events per activity, and cases containing it. The two differ when an activity repeats within a case.
- **Directly-Follows Graph (DFG):** for every pair (A, B), the number of times B came *immediately* after A within the same case. It is computed in pandas (`process_discovery.compute_dfg`) and cross-checked against `pm4py.discover_dfg` in the tests. It is drawn as a matrix (rows = from, columns = to), which is easier to read than a "spaghetti" diagram for 11 activities and needs no Graphviz installation.
- **Petri nets:** `pm4py.discover_petri_net_inductive` (default; produces a sound model) or `pm4py.discover_petri_net_heuristics` (used in the original notebook; more tolerant of noise). A discovered model describes what happened, not what should happen.

## 4. Variant analysis

A variant is a distinct activity sequence. `variant_analysis.variant_table` counts cases per variant with a pandas `groupby` and reports each variant's share of cases and the cumulative share.

> The original notebook failed on `pm4py.statistics.variants.log.get.get_variant_statistics`. This function does not exist in PM4Py 2.7.x (checked in 2.7.23.11: the module offers `get_variants`, `get_variants_sorted_by_count` and others). `pm4py.get_variants` exists but has changed its return type between versions (lists of traces vs. counts). A groupby avoids that dependency entirely.

## 5. Performance analysis

Three time measures are kept separate:

| Measure | Definition | Function |
|---|---|---|
| **Case duration** | Last event time minus first event time, in the prepared order | `case_durations` |
| **Transition gap** | Time from an event to the next event in the same case. Includes waiting and hand-over, so it is **not** the processing time of either activity. | `transition_gaps`, `transition_gap_summary` |
| **Activity processing time** | Start to end of one activity | **Not computed.** The data has one timestamp per event. |

All values are in **hours** (float). The original notebook mixed seconds, minutes and hours across cells.

**Statistics.** Summary statistics (`summarize_durations`) use only valid values. Missing values, negative values and single-event cases (which always have duration 0) are excluded, and each excluded group is **counted and reported**. Transitions are ranked by **median**, not mean, because waiting times are right-skewed. A transition must have been observed at least `MIN_TRANSITION_COUNT` (10) times to be ranked. Without that threshold, the top of the ranking was taken by transitions seen once, created when a rejected row joined its neighbours into a transition that never happened.

**Long-running cases:** cases above the 90th percentile of valid durations.

## 6. Conformance checking

- **Reference model:** a sequential Petri net built from `config.EXPECTED_ACTIVITIES` (`build_sequential_net`). This order is the *dominant observed path* in the original data, not an approved SOP. Results therefore mean "agreement with the usual path".
- **Vocabulary check first:** `vocabulary_check` lists activity names found only in the log or only in the model. The original notebook's "ideal" model used names such as `Pharmacy Request Sent` and `Final Physician Sign-off` that never occur in the log, so replaying against it could not produce a meaningful result.
- **Token-based replay** (`pm4py.fitness_token_based_replay` and `pm4py.conformance_diagnostics_token_based_replay`): reports the percentage of perfectly fitting cases, the average case fitness, the log fitness, and per-case missing and remaining tokens.
- **Precedence rules** (`check_precedence`): a simple "B requires an earlier A" check for when only a few business rules are known. The project does not assume any rule.

**What conformance cannot show here.** Replaying a log on a model discovered from the same log measures the discovery algorithm, not compliance. The original notebook's fitness of 1.00 came from replaying the 108 cases of a single variant on a model discovered from those same 108 cases. A compliance claim requires an independent reference model.

## 7. Synthetic data as a correctness check

The synthetic generator (`synthetic_data.py`) uses known rules: designed median gaps, step-skip, swap and rework probabilities, and an exact number of injected data-quality problems. Tests confirm that the pipeline:

- reports exactly the injected numbers of missing, invalid and duplicate records;
- produces no negative durations on clean synthetic data;
- ranks the designed slowest step (`→ Patient Transport Arranged`, median 150 min) first, at 2.5 h ± 25%.

This tests the *method*, not only that the code runs.
