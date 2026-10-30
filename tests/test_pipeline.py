"""End-to-end tests on the synthetic data, including output generation.

Because the synthetic generator's rules are known, these tests check that
the analysis recovers them, which is a check of the method and not only that
the code runs.
"""

import pandas as pd
import pytest

from healthcare_process_mining import config
from healthcare_process_mining.pipeline import run_analysis, write_outputs
from healthcare_process_mining.synthetic_data import generate_clean_log, inject_quality_issues

pytestmark = pytest.mark.pm4py


@pytest.fixture(scope="module")
def synthetic():
    clean = generate_clean_log(n_cases=120, seed=7)
    dirty, injected = inject_quality_issues(clean, seed=7)
    return clean, dirty, injected


def test_generator_is_reproducible():
    pd.testing.assert_frame_equal(generate_clean_log(20, seed=1), generate_clean_log(20, seed=1))


def test_validation_finds_exactly_the_injected_problems(synthetic):
    _, dirty, injected = synthetic
    results = run_analysis(dirty, timestamp_provenance="synthetic")
    report = results.validation

    for check, expected in injected.items():
        assert report.get(check) == expected, check
    assert report.get("unexpected_activity") == 0
    # The file was shuffled, so many cases are out of time order in the file.
    assert report.get("case_order_conflict") > 0


def test_record_counts_add_up(synthetic):
    clean, dirty, injected = synthetic
    counts = run_analysis(dirty, timestamp_provenance="synthetic").preparation.counts

    rejected = sum(injected[k] for k in ["missing_timestamp", "invalid_timestamp", "missing_activity", "missing_case_id"])
    assert counts["loaded"] == len(clean) + injected["exact_duplicate"]
    assert counts["rejected"] == rejected
    assert counts["retained"] == counts["loaded"] - counts["rejected"]


def test_clean_synthetic_durations_are_never_negative(synthetic):
    clean, _, _ = synthetic
    results = run_analysis(clean, timestamp_provenance="synthetic")
    assert results.duration_summary["n_negative"] == 0
    assert results.transition_gap_summary["n_negative"].sum() == 0


def test_recovers_the_designed_slowest_step(synthetic):
    clean, _, _ = synthetic
    gaps = run_analysis(clean, timestamp_provenance="synthetic").transition_gap_summary
    common = gaps[gaps["count"] >= 20]
    # The generator gives "Patient Transport Arranged" the longest median wait (150 min).
    top = common.iloc[0]
    assert top["target"] == "Patient Transport Arranged"
    assert top["median_hours"] == pytest.approx(2.5, rel=0.25)


def test_unreliable_timestamps_skip_performance(synthetic):
    _, dirty, _ = synthetic
    results = run_analysis(dirty, timestamp_provenance="unreliable")

    assert results.order_by == "file_order"
    assert not results.performance_available
    assert any("unreliable" in note for note in results.notes)
    # Rows without a valid timestamp are kept for control-flow analysis.
    assert results.preparation.counts["rejected"] == 3  # 2 missing activity + 1 missing case


def test_conformance_against_reference(synthetic):
    clean, _, _ = synthetic
    results = run_analysis(clean, timestamp_provenance="synthetic", reference_activities=config.EXPECTED_ACTIVITIES)
    m = results.conformance_metrics
    assert 0 < m["perc_fit_traces"] < 100  # some cases follow the full path, some deviate
    assert results.vocabulary["only_in_log"] == []


def test_invalid_provenance_and_missing_columns_raise(synthetic):
    clean, _, _ = synthetic
    with pytest.raises(ValueError, match="timestamp_provenance"):
        run_analysis(clean, timestamp_provenance="probably fine")
    with pytest.raises(ValueError, match="missing columns"):
        run_analysis(clean.drop(columns=["Activity"]), timestamp_provenance="synthetic")


def test_write_outputs_creates_reports_and_figures(synthetic, tmp_path):
    _, dirty, _ = synthetic
    results = run_analysis(dirty, timestamp_provenance="synthetic", reference_activities=config.EXPECTED_ACTIVITIES)
    written = write_outputs(results, tmp_path)

    for name in ["report", "variants", "rejected_records", "fig_dfg_matrix", "fig_case_durations"]:
        assert written[name].is_file() and written[name].stat().st_size > 0, name
    report = written["report"].read_text(encoding="utf-8")
    assert f"Loaded: {results.preparation.counts['loaded']:,} rows" in report
    assert "synthetic" in report.lower()
    rejected = pd.read_csv(written["rejected_records"])
    assert len(rejected) == results.preparation.counts["rejected"]


def test_report_states_when_performance_is_not_established(synthetic, tmp_path):
    _, dirty, _ = synthetic
    written = write_outputs(run_analysis(dirty, timestamp_provenance="unreliable"), tmp_path)
    assert "Not established" in written["report"].read_text(encoding="utf-8")
    assert "fig_case_durations" not in written
