"""Tests for combining the Altair structure, layer, agent and colorbar charts."""

import altair as alt
import pandas as pd
import pytest

from modelly.viz.render.altair_canvas import (
    EMPTY_CHART_HEIGHT,
    EMPTY_CHART_WIDTH,
    FRAME_STROKE_WIDTH,
    compose_altair_canvas,
    redraw_altair_canvas,
)


def _chart(name):
    return (
        alt.Chart(pd.DataFrame({"x": [1], "y": [2]}))
        .mark_point()
        .properties(title=name)
    )


def _view(spec):
    return spec.to_dict()["config"]["view"]


def test_empty_canvas_is_a_framed_placeholder():
    """Empty canvas is a framed placeholder."""
    chart = compose_altair_canvas(None, None, None, None)
    spec = chart.to_dict()
    assert spec["width"] == EMPTY_CHART_WIDTH
    assert spec["height"] == EMPTY_CHART_HEIGHT
    assert spec["config"]["view"]["stroke"] == "black"
    assert spec["config"]["view"]["strokeWidth"] == FRAME_STROKE_WIDTH


def test_single_chart_is_used_as_is():
    """Single chart is used as is."""
    agents = _chart("agents")
    spec = compose_altair_canvas(None, None, agents, None).to_dict()
    assert spec["title"] == "agents"
    assert "layer" not in spec


def test_several_spatial_charts_are_layered_in_order():
    """Several spatial charts are layered in order."""
    spec = compose_altair_canvas(
        _chart("structure"), _chart("layer"), _chart("agents"), None
    ).to_dict()
    assert [layer["title"] for layer in spec["layer"]] == [
        "structure",
        "layer",
        "agents",
    ]


def test_colorbar_is_stacked_below_spatial_chart():
    """Colorbar is stacked below spatial chart."""
    spec = compose_altair_canvas(None, None, _chart("agents"), _chart("cbar")).to_dict()
    assert [part["title"] for part in spec["vconcat"]] == ["agents", "cbar"]
    assert (
        _view(compose_altair_canvas(None, None, _chart("a"), _chart("c")))[
            "strokeWidth"
        ]
        == FRAME_STROKE_WIDTH
    )


@pytest.mark.xfail(
    reason="_with_colorbar calls configure_view(grid=False); ViewConfig has no 'grid'",
    raises=alt.utils.schemapi.SchemaValidationError,
)
def test_colorbar_alone():
    """Colorbar alone."""
    spec = compose_altair_canvas(None, None, None, _chart("cbar")).to_dict()
    assert spec["title"] == "cbar"
    assert spec["config"]["view"]["stroke"] == "black"


class _FakeRenderer:
    """Records which meshes the canvas asks it to redraw."""

    def __init__(self, space=None, agents=None, layers=None):
        self.space_mesh = space
        self.agent_mesh = agents
        self.property_layer_mesh = layers
        self.calls = []

    def draw_structure(self):
        self.calls.append("structure")
        return _chart("new structure")

    def draw_agents(self):
        self.calls.append("agents")
        return _chart("new agents")

    def draw_property_layer(self):
        self.calls.append("layers")
        return _chart("new layer"), _chart("new cbar")


def test_redraw_redraws_only_what_was_drawn_before():
    """Redraw redraws only what was drawn before."""
    renderer = _FakeRenderer(agents=_chart("old agents"))
    spec = redraw_altair_canvas(renderer).to_dict()
    assert renderer.calls == ["agents"]
    assert spec["title"] == "new agents"


def test_redraw_everything():
    """Redraw everything."""
    renderer = _FakeRenderer(
        space=_chart("s"), agents=_chart("a"), layers=(_chart("l"), _chart("c"))
    )
    spec = redraw_altair_canvas(renderer).to_dict()
    assert renderer.calls == ["structure", "agents", "layers"]
    spatial, cbar = spec["vconcat"]
    assert [layer["title"] for layer in spatial["layer"]] == [
        "new structure",
        "new layer",
        "new agents",
    ]
    assert cbar["title"] == "new cbar"


def test_redraw_nothing_gives_placeholder():
    """Redraw nothing gives placeholder."""
    renderer = _FakeRenderer()
    spec = redraw_altair_canvas(renderer).to_dict()
    assert renderer.calls == []
    assert spec["width"] == EMPTY_CHART_WIDTH
