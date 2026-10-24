"""Tests for the publication styles and the colour-blind-safe palettes."""

import io

import matplotlib as mpl
import pytest
from matplotlib.figure import Figure

from modelly.viz import styles
from modelly.viz.palettes import OKABE_ITO, PALETTES

MM_PER_INCH = 25.4


def test_nature_widths_in_inches():
    """Nature: 89 mm single column, 183 mm double."""
    single, height = styles.figure_size("nature", 1)
    assert single == pytest.approx(89 / MM_PER_INCH)
    assert height == pytest.approx(single / styles.GOLDEN_RATIO)
    assert styles.figure_size("nature", 2)[0] == pytest.approx(183 / MM_PER_INCH)


@pytest.mark.parametrize("journal", sorted(styles.JOURNALS))
def test_every_journal_has_a_wider_double_column(journal):
    """Every journal's double column is wider than its single column."""
    widths = styles.JOURNALS[journal]
    assert 0 < widths.single < widths.double


def test_aspect_sets_the_height():
    """Aspect is width over height."""
    width, height = styles.figure_size("ieee", 1, aspect=1.0)
    assert width == height == pytest.approx(3.5)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: styles.figure_size("tabloid"), "unknown journal"),
        (lambda: styles.figure_size("nature", 3), "columns must be 1 or 2"),
        (lambda: styles.rc_params(palette="rainbow"), "unknown palette"),
    ],
)
def test_bad_arguments(call, message):
    """Unknown journals, palettes and column counts are refused."""
    with pytest.raises(ValueError, match=message):
        call()


def test_paper_sets_and_restores_the_settings():
    """Inside the block the style holds; after it, the previous settings are back."""
    before = mpl.rcParams["figure.figsize"]
    with styles.paper("pnas", columns=2, palette="tol_bright") as params:
        assert tuple(mpl.rcParams["figure.figsize"]) == pytest.approx(
            params["figure.figsize"]
        )
        assert mpl.rcParams["pdf.fonttype"] == styles.TRUETYPE
        colours = [c["color"] for c in mpl.rcParams["axes.prop_cycle"]]
        assert colours == list(PALETTES["tol_bright"])
    assert mpl.rcParams["figure.figsize"] == before


def test_a_figure_made_in_the_block_saves_as_pdf():
    """A figure drawn in the style saves as a PDF with embedded TrueType fonts."""
    with styles.paper():
        figure = Figure()
        figure.add_subplot().plot([0, 1], [1, 0], label="a")
        buffer = io.BytesIO()
        figure.savefig(buffer, format="pdf")
    assert buffer.getvalue().startswith(b"%PDF")
    assert figure.get_size_inches()[0] == pytest.approx(89 / MM_PER_INCH)


def test_palettes_are_hex_colours():
    """Every palette entry is a #RRGGBB string, Okabe-Ito has eight."""
    assert len(OKABE_ITO) == 8
    for palette in PALETTES.values():
        assert all(len(c) == 7 and c.startswith("#") for c in palette)
        assert len(set(palette)) == len(palette)
