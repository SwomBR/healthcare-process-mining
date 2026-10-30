"""Reusable charts.

Every function here receives results that were already calculated by the
analysis modules and only draws them. No metric is computed inside a plotting
function, so a chart can never disagree with the numbers in the report.

All core charts use matplotlib only. Rendering PM4Py's own DFG and Petri-net
diagrams additionally needs the Graphviz program (not just the Python
package). Those functions are optional and raise a clear error if Graphviz
is missing.
"""

import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to files; works on servers and CI without a display
import matplotlib.pyplot as plt
import pandas as pd

BAR_COLOR = "#2a78d6"
TEXT_COLOR = "#0b0b0b"
MUTED_TEXT = "#52514e"
GRID_COLOR = "#e4e3df"
BACKGROUND = "#fcfcfb"


def _new_axes(width: float, height: float):
    fig, ax = plt.subplots(figsize=(width, height), facecolor=BACKGROUND)
    ax.set_facecolor(BACKGROUND)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID_COLOR)
    ax.tick_params(colors=MUTED_TEXT)
    ax.set_axisbelow(True)
    return fig, ax


def _note(fig, text: str) -> None:
    """Add a small footnote, used for data-quality caveats."""
    fig.text(0.01, 0.01, text, fontsize=8, color=MUTED_TEXT, ha="left", va="bottom")


def _horizontal_bars(labels, values, title: str, xlabel: str, value_format: str = "{:,.0f}"):
    fig, ax = _new_axes(10, max(3.0, 0.45 * len(labels) + 1.5))
    positions = range(len(labels))
    ax.barh(positions, values, color=BAR_COLOR, height=0.6)
    ax.set_yticks(list(positions), labels, color=TEXT_COLOR)
    ax.invert_yaxis()  # largest value on top
    ax.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax.set_xlabel(xlabel, color=MUTED_TEXT)
    ax.set_title(title, loc="left", color=TEXT_COLOR, fontweight="bold")
    for position, value in zip(positions, values):
        ax.text(value, position, " " + value_format.format(value), va="center", fontsize=8, color=MUTED_TEXT)
    return fig, ax


def plot_activity_frequency(frequency: pd.DataFrame):
    """Bar chart of events per activity (output of ``activity_frequency``)."""
    fig, _ = _horizontal_bars(frequency["activity"], frequency["event_count"],
                              "Events per activity", "Number of events")
    fig.tight_layout()
    return fig


def plot_variant_coverage(variants: pd.DataFrame, top_n: int = 10):
    """Bar chart of the share of cases covered by the most frequent variants."""
    top = variants.head(top_n)
    # Variants share long common prefixes, so a truncated path would hide the
    # difference. Label by ID and length; full paths are in the variant table.
    labels = [f"Variant {vid} ({n} activities)" for vid, n in zip(top["variant_id"], top["n_activities"])]
    fig, _ = _horizontal_bars(labels, top["case_pct"], f"Top {len(top)} process variants",
                              "Share of cases (%)", "{:.1f}%")
    _note(fig, f"{len(variants)} distinct variants in total; the top {len(top)} cover "
               f"{top['case_pct'].sum():.1f}% of cases. Full paths: outputs/reports/variants.csv.")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def plot_case_duration_histogram(durations: pd.DataFrame, summary: dict, provenance_note: str = ""):
    """Histogram of valid case durations, with the excluded counts stated on the chart.

    Args:
        durations: Output of ``case_durations``.
        summary: Output of ``summarize_durations`` for the same table.
        provenance_note: Text describing where the timestamps came from.
    """
    valid = durations[(durations["duration_hours"] >= 0) & ~durations["is_single_event"]]["duration_hours"]
    fig, ax = _new_axes(9, 4.5)
    ax.hist(valid, bins=30, color=BAR_COLOR, edgecolor=BACKGROUND, linewidth=1)
    ax.axvline(summary["median"], color=TEXT_COLOR, linewidth=1.5, linestyle="--")
    ax.text(summary["median"], ax.get_ylim()[1] * 0.95, f"  median {summary['median']:.1f} h",
            color=TEXT_COLOR, fontsize=9, va="top")
    ax.yaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax.set_xlabel("Case duration (hours)", color=MUTED_TEXT)
    ax.set_ylabel("Number of cases", color=MUTED_TEXT)
    ax.set_title("Case duration distribution", loc="left", color=TEXT_COLOR, fontweight="bold")
    _note(fig, f"{summary['n_valid']} cases shown. Excluded: {summary['n_single_event']} single-event, "
               f"{summary['n_negative']} negative, {summary['n_missing']} missing. {provenance_note}")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return fig


def plot_transition_gaps(top: pd.DataFrame, provenance_note: str = ""):
    """Bar chart of transitions by median time between events.

    Args:
        top: Rows to draw, typically the output of ``slowest_transitions``.
        provenance_note: Text describing where the timestamps came from.
    """
    labels = [f"{source} -> {target}" for source, target in zip(top["source"], top["target"])]
    fig, _ = _horizontal_bars(labels, top["median_hours"], "Longest median time between consecutive events",
                              "Median hours (waiting + work on the next step, not processing time)", "{:.2f} h")
    _note(fig, provenance_note)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def plot_dfg_matrix(dfg: pd.DataFrame, activity_order: list[str] | None = None):
    """Draw the Directly-Follows Graph as a matrix: row = from, column = to.

    For a process with about ten activities, a matrix is easier to read than
    a "spaghetti" diagram and needs no Graphviz. Each cell shows how often
    the column activity directly followed the row activity.

    Args:
        dfg: Output of ``compute_dfg``.
        activity_order: Row and column order. Defaults to alphabetical.
    """
    activities = activity_order or sorted(set(dfg["source"]) | set(dfg["target"]))
    present = set(dfg["source"]) | set(dfg["target"])
    activities = [a for a in activities if a in present] + sorted(present - set(activities))
    matrix = (dfg.pivot_table(index="source", columns="target", values="count", aggfunc="sum")
              .reindex(index=activities, columns=activities).fillna(0))

    size = max(6.0, 0.6 * len(activities) + 3)
    fig, ax = plt.subplots(figsize=(size + 1, size), facecolor=BACKGROUND)
    image = ax.imshow(matrix.values, cmap="Blues", vmin=0)
    ax.set_xticks(range(len(activities)), activities, rotation=45, ha="right", fontsize=8, color=TEXT_COLOR)
    ax.set_yticks(range(len(activities)), activities, fontsize=8, color=TEXT_COLOR)
    ax.set_xlabel("Next activity", color=MUTED_TEXT)
    ax.set_ylabel("Activity", color=MUTED_TEXT)
    threshold = matrix.values.max() / 2 if matrix.values.size else 0
    for i in range(len(activities)):
        for j in range(len(activities)):
            value = int(matrix.values[i, j])
            if value:
                ax.text(j, i, f"{value:,}", ha="center", va="center", fontsize=7,
                        color="white" if value > threshold else TEXT_COLOR)
    ax.set_title("Directly-follows counts", loc="left", color=TEXT_COLOR, fontweight="bold")
    fig.colorbar(image, ax=ax, shrink=0.7, label="Number of transitions")
    fig.tight_layout()
    return fig


def save_figure(fig, path: str | Path, dpi: int = 150) -> Path:
    """Save a figure as an image (creating folders as needed) and close it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return path


def graphviz_available() -> bool:
    """Return True if the Graphviz ``dot`` program is installed and on PATH."""
    return shutil.which("dot") is not None


def _require_graphviz() -> None:
    if not graphviz_available():
        raise RuntimeError(
            "Graphviz is not installed, so PM4Py cannot render diagrams. Install it from "
            "https://graphviz.org/download/ and make sure 'dot' is on your PATH. "
            "The matplotlib charts in this module do not need it."
        )


def save_dfg_diagram(dfg: pd.DataFrame, starts: pd.Series, ends: pd.Series, path: str | Path) -> Path:
    """Render the DFG as a PM4Py/Graphviz diagram (requires Graphviz).

    Raises:
        RuntimeError: If Graphviz is not installed.
    """
    import pm4py

    _require_graphviz()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    edges = {(s, t): int(c) for s, t, c in zip(dfg["source"], dfg["target"], dfg["count"])}
    pm4py.save_vis_dfg(edges, starts.to_dict(), ends.to_dict(), str(path))
    return path


def save_petri_net_diagram(net, initial_marking, final_marking, path: str | Path) -> Path:
    """Render a Petri net with PM4Py/Graphviz (requires Graphviz).

    Raises:
        RuntimeError: If Graphviz is not installed.
    """
    import pm4py

    _require_graphviz()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pm4py.save_vis_petri_net(net, initial_marking, final_marking, str(path))
    return path
