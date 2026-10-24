"""Publication styles for Matplotlib: journal column widths and colour-blind-safe palettes.

``paper()`` is a context manager that sets Matplotlib up for a figure in a journal: the
figure is one or two columns wide, the fonts are small and embedded as TrueType, the colour
cycle is colour-blind safe and figures are saved at print resolution::

    from modelly.viz import styles

    with styles.paper("nature", columns=2):
        fig, ax = plt.subplots()
        ax.plot(df["Gini"])
        fig.savefig("gini.pdf")

The widths are those the journals' author guides state; check the current guide before
submitting. ``figure_size`` gives the size alone, and ``rc_params`` the settings as a dict.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, NamedTuple

import matplotlib as mpl
from cycler import cycler

from modelly.viz.palettes import PALETTES

MM_PER_INCH = 25.4
GOLDEN_RATIO = (1 + 5**0.5) / 2
PRINT_DPI = 300
BASE_FONT_SIZE = 8
SMALL_FONT_SIZE = 7
LINE_WIDTH = 1.0
AXES_LINE_WIDTH = 0.6
# TrueType fonts in PDF and PostScript, which journals require (Type 3 is refused).
TRUETYPE = 42


class ColumnWidths(NamedTuple):
    """A journal's figure widths, in inches."""

    single: float
    double: float


def _mm(single: float, double: float) -> ColumnWidths:
    """Column widths given in millimetres, in inches."""
    return ColumnWidths(single / MM_PER_INCH, double / MM_PER_INCH)


JOURNALS: dict[str, ColumnWidths] = {
    "nature": _mm(89, 183),
    "science": _mm(57, 121),
    "pnas": _mm(87, 178),
    "elsevier": _mm(90, 190),
    "plos": ColumnWidths(5.2, 7.5),
    "ieee": ColumnWidths(3.5, 7.16),
}


def figure_size(
    journal: str = "nature", columns: int = 1, aspect: float = GOLDEN_RATIO
) -> tuple[float, float]:
    """The ``(width, height)`` in inches of a figure ``columns`` wide in ``journal``.

    Args:
        journal: A key of ``JOURNALS``.
        columns: 1 for a single column, 2 for the full page width.
        aspect: Width divided by height; the golden ratio by default.

    Raises:
        ValueError: For an unknown journal or a column count other than 1 or 2.
    """
    if journal not in JOURNALS:
        raise ValueError(f"unknown journal {journal!r}; known: {', '.join(JOURNALS)}")
    if columns not in (1, 2):
        raise ValueError(f"columns must be 1 or 2, got {columns}")
    widths = JOURNALS[journal]
    width = widths.single if columns == 1 else widths.double
    return width, width / aspect


def rc_params(
    journal: str = "nature", columns: int = 1, palette: str = "okabe_ito"
) -> dict[str, Any]:
    """The Matplotlib settings ``paper`` applies, as a dict for ``plt.rc_context``.

    Raises:
        ValueError: For an unknown journal, palette or column count.
    """
    if palette not in PALETTES:
        raise ValueError(f"unknown palette {palette!r}; known: {', '.join(PALETTES)}")
    return {
        "figure.figsize": figure_size(journal, columns),
        "figure.dpi": PRINT_DPI,
        "savefig.dpi": PRINT_DPI,
        "savefig.bbox": "tight",
        "font.size": BASE_FONT_SIZE,
        "axes.titlesize": BASE_FONT_SIZE,
        "axes.labelsize": BASE_FONT_SIZE,
        "xtick.labelsize": SMALL_FONT_SIZE,
        "ytick.labelsize": SMALL_FONT_SIZE,
        "legend.fontsize": SMALL_FONT_SIZE,
        "legend.frameon": False,
        "lines.linewidth": LINE_WIDTH,
        "axes.linewidth": AXES_LINE_WIDTH,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.prop_cycle": cycler(color=list(PALETTES[palette])),
        "pdf.fonttype": TRUETYPE,
        "ps.fonttype": TRUETYPE,
    }


@contextmanager
def paper(
    journal: str = "nature", columns: int = 1, palette: str = "okabe_ito"
) -> Iterator[dict[str, Any]]:
    """Draw the figures made inside the block in a journal's style.

    Args:
        journal: A key of ``JOURNALS``: ``nature``, ``science``, ``pnas``, ``elsevier``,
            ``plos`` or ``ieee``.
        columns: 1 for a single column, 2 for the full page width.
        palette: A key of ``modelly.viz.palettes.PALETTES``, the colour cycle.

    Yields:
        The settings applied, which are undone when the block ends.
    """
    params = rc_params(journal, columns, palette)
    with mpl.rc_context(params):
        yield params


__all__ = ["JOURNALS", "ColumnWidths", "figure_size", "paper", "rc_params"]
