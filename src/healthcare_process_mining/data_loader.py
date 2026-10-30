"""Load raw event data from disk.

This module is the only place that reads input files. It checks that the
file exists and is a supported format, and returns the records exactly as
stored: every column is read as text, so no value is silently converted
(for example, a case ID such as "00123" keeps its leading zeros). Parsing
and cleaning happen later, in ``data_preparation``.
"""

from pathlib import Path

import pandas as pd

SUPPORTED_EXTENSIONS = {".csv"}


def load_event_data(file_path: str | Path) -> pd.DataFrame:
    """Load event records from a CSV file.

    Args:
        file_path: Path to the source CSV file.

    Returns:
        A DataFrame with one row per record. All values are strings, and
        empty cells are ``NaN``.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file extension is not supported, or the file
            is empty or has no header row.
    """
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Event data file not found: {path}. "
            "See data/README.md for where to place input files."
        )

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{path.suffix}'. "
            f"Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        )

    try:
        # utf-8-sig also accepts files saved with a byte-order mark, which the
        # original notebook wrote (encoding="utf-8-sig").
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"Event data file is empty: {path}") from error

    # Strip stray spaces from headers such as " Activity" so the column map
    # still matches.
    df.columns = [str(column).strip() for column in df.columns]
    return df
