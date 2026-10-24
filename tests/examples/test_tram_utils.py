"""Tests for the Tram Route Model drawing helpers."""

from types import SimpleNamespace

import matplotlib
import pytest
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch, Rectangle

from modelly.examples.behaviour.tram_model.utils import (
    HEADLIGHT_COLOR,
    LABEL_SIZE,
    PHASE_COLORS,
    PLATFORM_COLOR,
    TRIM_COLOR,
    draw_track,
    draw_track_view,
    draw_tram,
    phase,
    tram_portrayal,
)

ROUTE = [0.0, 400.0, 1000.0]


def _tram(acceleration=0.0, speed=0.0, complete=False, position=400.0):
    return SimpleNamespace(
        route_complete=complete,
        acceleration=acceleration,
        speed=speed,
        position=position,
    )


@pytest.mark.parametrize(
    ("tram", "expected"),
    [
        (_tram(complete=True, acceleration=1.0), "route complete"),
        (_tram(acceleration=0.5), "accelerating"),
        (_tram(acceleration=-0.5, speed=3.0), "braking"),
        (_tram(speed=4.0), "coasting"),
        (_tram(), "dwelling at station"),
    ],
)
def test_phase(tram, expected):
    """Phase."""
    assert phase(tram) == expected


def test_tram_portrayal():
    """Tram portrayal."""
    style = tram_portrayal(_tram(acceleration=-1.0, speed=2.0, position=123.0))
    assert style == {
        "phase": "braking",
        "position": 123.0,
        "color": PHASE_COLORS["braking"],
        "edgecolor": TRIM_COLOR,
        "linewidth": 1.1,
        "zorder": 4,
    }


def _ax():
    return Figure().add_subplot()


def test_draw_track_sleepers_rail_and_platforms():
    """Draw track sleepers rail and platforms."""
    ax = _ax()
    span = ROUTE[-1] - ROUTE[0]
    draw_track(ax, ROUTE, span)
    platforms = [p for p in ax.patches if isinstance(p, Rectangle)]
    assert len(platforms) == len(ROUTE)
    assert all(
        p.get_facecolor()[:3] == matplotlib.colors.to_rgb(PLATFORM_COLOR)
        for p in platforms
    )
    # Platforms are centred on the stations and never wider than 30% of a gap.
    widths = {round(p.get_width(), 6) for p in platforms}
    assert widths == {round(min(span * 0.018, span / 2 * 0.3), 6)}
    centres = [p.get_x() + p.get_width() / 2 for p in platforms]
    assert centres == pytest.approx(ROUTE)
    # about 90 sleepers plus the rail line
    assert 88 <= len(ax.lines) - 1 <= 92


def test_draw_track_single_station():
    """Draw track single station."""
    ax = _ax()
    draw_track(ax, [5.0], 10.0)
    assert len([p for p in ax.patches if isinstance(p, Rectangle)]) == 1


@pytest.mark.parametrize(("heading", "nose_fraction"), [(3.0, 0.94), (-3.0, 0.06)])
def test_draw_tram_body_windows_and_headlight(heading, nose_fraction):
    """Draw tram body windows and headlight."""
    ax = _ax()
    style = tram_portrayal(_tram(speed=abs(heading), position=500.0))
    draw_tram(ax, style, ROUTE, heading)
    [body] = [p for p in ax.patches if isinstance(p, FancyBboxPatch)]
    assert body.get_facecolor()[:3] == matplotlib.colors.to_rgb(style["color"])
    margin = 1000 * 0.04
    centre = (500.0 + margin) / (1000 + 2 * margin)
    assert body.get_x() + body.get_width() / 2 == pytest.approx(centre)
    rectangles = [p for p in ax.patches if type(p) is Rectangle]
    assert len(rectangles) == 5  # skirt plus four windows
    [headlight] = [line for line in ax.lines if line.get_color() == HEADLIGHT_COLOR]
    left = centre - 0.07 / 2
    assert headlight.get_xdata()[0] == pytest.approx(left + 0.07 * nose_fraction)
    assert len(ax.lines) == 4  # headlight, wheels, pantograph arm and bar


def test_draw_track_view_sets_up_axis():
    """Draw track view sets up axis."""
    ax = _ax()
    tram = _tram(speed=2.0, position=250.0)
    model = SimpleNamespace(route=ROUTE, tram=tram)
    draw_track_view(ax, model, tram_portrayal(tram))
    margin = 1000 * 0.04
    assert ax.get_xlim() == pytest.approx((-margin, 1000 + margin))
    assert ax.get_ylim() == pytest.approx((0.1, 0.95))
    assert list(ax.get_yticks()) == []
    assert ax.get_xlabel() == "position along route (m)"
    assert ax.xaxis.label.get_fontsize() == LABEL_SIZE
    assert not ax.spines["top"].get_visible()
    assert ax.spines["bottom"].get_visible()
    assert any(isinstance(p, FancyBboxPatch) for p in ax.patches)
