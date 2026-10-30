# Data

| Folder | Contents | In Git? |
|---|---|---|
| `sample/` | `synthetic_discharge_events.csv`: **synthetic** demo data | Yes |
| `raw/` | Your own event-log extracts | **No** (gitignored) |

## `sample/synthetic_discharge_events.csv` (SYNTHETIC)

Every value in this file is invented. It was created by
`python -m healthcare_process_mining.synthetic_data` (seed 42) and contains:

- 500 cases (`SYN-00001` ... `SYN-00500`), 5,243 rows, in Q1 2024 (a made-up period);
- the 11 activity names of the original capstone dataset;
- invented process variation: optional steps (30% and 10%), two steps swapped (20%),
  a second physician signature (12%) and incomplete cases (5%);
- invented waiting times (log-normal; medians in `synthetic_data.TRANSITION_MEDIAN_MINUTES`);
- **deliberately injected data-quality problems**: 3 missing timestamps, 2 invalid
  timestamps, 2 missing activities, 1 missing case ID, 4 exact duplicates, and rows
  shuffled out of time order.

It shows that the pipeline works. It contains no information about any real hospital or patient.

## Using your own data (`raw/`)

Place a CSV in `data/raw/` with at least these columns (names as in the original dataset):

| Column | Meaning |
|---|---|
| `Case ID` | One discharge encounter |
| `Activity` | Name of the step |
| `Timestamp` | When the step was recorded, `YYYY-MM-DD HH:MM:SS` |

Then run:

```bash
python -m healthcare_process_mining --input data/raw/your_file.csv --timestamps original
```

Use `--timestamps original` only if the times come from the source system. Never commit
real patient data. `data/raw/` is gitignored for this reason.

## The original capstone dataset

`discharge_events.csv` (13,710 rows, 2,500 cases) is **not available**. Its source was not
documented, and the original notebook replaced its timestamps with random values. See
`docs/data_dictionary.md` and `docs/findings_and_limitations.md`.
