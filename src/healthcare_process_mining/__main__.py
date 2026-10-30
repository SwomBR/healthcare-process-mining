"""Command-line entry point.

Examples (run from the project root after ``pip install -e .``)::

    # Demo on the bundled synthetic data
    python -m healthcare_process_mining --input data/sample/synthetic_discharge_events.csv --timestamps synthetic

    # Your own extract with real system timestamps
    python -m healthcare_process_mining --input data/raw/discharge_events.csv --timestamps original
"""

import argparse

from . import config
from .pipeline import run_analysis, write_outputs


def main(argv: list[str] | None = None) -> None:
    """Parse arguments, run the analysis and print where the outputs went."""
    parser = argparse.ArgumentParser(description="Discharge-process mining with data-quality checks.")
    parser.add_argument("--input", default=str(config.SYNTHETIC_SAMPLE_FILE), help="Event log CSV file.")
    parser.add_argument("--timestamps", required=True, choices=list(config.TIMESTAMP_PROVENANCE_OPTIONS),
                        help="Where the timestamps came from; controls whether timing results are produced.")
    parser.add_argument("--order-by", choices=["timestamp", "file_order"], default=None,
                        help="Event ordering within cases (default depends on --timestamps).")
    parser.add_argument("--output", default=str(config.OUTPUT_DIR), help="Output folder.")
    parser.add_argument("--drop-duplicates", action="store_true", help="Drop exact duplicate events.")
    parser.add_argument("--no-conformance", action="store_true", help="Skip conformance checking.")
    args = parser.parse_args(argv)

    results = run_analysis(
        args.input,
        timestamp_provenance=args.timestamps,
        order_by=args.order_by,
        reference_activities=None if args.no_conformance else config.EXPECTED_ACTIVITIES,
        drop_exact_duplicates=args.drop_duplicates,
    )
    written = write_outputs(results, args.output)

    counts = results.preparation.counts
    print(f"Loaded {counts['loaded']:,} rows, rejected {counts['rejected']:,}, analysed {counts['retained']:,}.")
    for note in results.notes:
        print(f"Note: {note}")
    print(f"Report: {written['report']}")


if __name__ == "__main__":
    main()
