"""Tests for the Altair property layer charts and the legacy space chart."""

from types import SimpleNamespace

import altair as alt
import numpy as np
import pytest

from modelly import Model
from modelly.space import CellAgent, OrthogonalMooreGrid
from modelly.space.continuous import ContinuousSpace, ContinuousSpaceAgent
from modelly.viz.altair.property_layers import (
    _gradient_endpoints,
    _Layer,
    _prepare_layer,
    _rgba_mapper,
    chart_property_layers,
)
from modelly.viz.altair.space_chart import (
    _agent_encoding,
    _draw_grid,
    _get_agent_data,
    _get_agent_data_continuous_space,
    _portrayal_to_dict,
    _tooltips,
)
from modelly.viz.components import AgentPortrayalStyle

CHART = 300


def _grid(width=4, height=3):
    model = Model(rng=7)
    grid = OrthogonalMooreGrid((width, height), random=model.random)
    return model, grid


def _layer_grid():
    model, grid = _grid()
    grid.create_property_layer("sugar", default_value=0.0)
    sugar = grid.property_layers["sugar"]
    sugar[:] = np.arange(12, dtype=float).reshape(4, 3)
    grid.create_property_layer("flag", default_value=False, dtype=bool)
    grid.property_layers["flag"][0, 0] = True
    return model, grid


def test_prepare_layer_long_form_and_defaults():
    """Prepare layer long form and defaults."""
    _, grid = _layer_grid()
    layer = _prepare_layer(grid, "sugar", grid.property_layers["sugar"], {})
    assert (layer.vmin, layer.vmax, layer.alpha, layer.colorbar) == (0, 11, 1, True)
    assert list(layer.df.columns) == ["x", "y", "value"]
    assert len(layer.df) == 12
    row = layer.df[(layer.df.x == 2) & (layer.df.y == 1)]
    assert row.value.item() == 7.0


def test_prepare_layer_bool_and_overrides():
    """Prepare layer bool and overrides."""
    _, grid = _layer_grid()
    portrayal = {"alpha": 0.5, "vmin": -1, "vmax": 2, "colorbar": False}
    layer = _prepare_layer(grid, "flag", grid.property_layers["flag"], portrayal)
    assert layer.df.value.dtype == float
    assert layer.df.value.sum() == 1.0
    assert (layer.alpha, layer.vmin, layer.vmax, layer.colorbar) == (0.5, -1, 2, False)


def test_prepare_layer_warns_on_shape_mismatch():
    """Prepare layer warns on shape mismatch."""
    _, grid = _grid()
    with pytest.warns(UserWarning, match="do not match space dimensions"):
        _prepare_layer(grid, "odd", np.zeros((2, 2)), {})


def test_rgba_mapper_scales_opacity_and_clamps():
    """Rgba mapper scales opacity and clamps."""
    layer = _Layer("l", None, alpha=0.5, vmin=0.0, vmax=10.0, colorbar=True)
    to_rgba = _rgba_mapper(layer, "red")
    assert to_rgba(10) == "rgba(255, 0, 0, 0.50)"
    assert to_rgba(5) == "rgba(255, 0, 0, 0.25)"
    assert to_rgba(-3) == "rgba(255, 0, 0, 0.00)"
    assert to_rgba(99) == "rgba(255, 0, 0, 0.50)"


def test_gradient_endpoints():
    """Gradient endpoints."""
    layer = _Layer("l", None, alpha=0.75, vmin=0, vmax=1, colorbar=True)
    assert _gradient_endpoints(layer, "blue") == (
        "rgba(0,0,255,0)",
        "rgba(0,0,255,0.75)",
    )


def test_color_layer_with_colorbar():
    """Color layer with colorbar."""
    _, grid = _layer_grid()
    base, cbar = chart_property_layers(
        grid, {"sugar": {"color": "green", "alpha": 0.8}}, CHART, CHART
    )
    spec = base.to_dict()
    assert spec["mark"]["type"] == "rect"
    assert spec["title"] == "sugar"
    assert spec["encoding"]["fill"]["scale"] is None
    values = next(iter(spec["datasets"].values()))
    assert values[-1]["color"] == "rgba(0, 128, 0, 0.80)"
    cbar_spec = cbar.to_dict()
    assert cbar_spec["height"] == 70
    assert len(cbar_spec["layer"]) == 4
    title_layer = cbar_spec["layer"][3]
    assert title_layer["mark"]["fontWeight"] == "bold"


def test_colormap_layer_without_colorbar_and_layering():
    """Colormap layer without colorbar and layering."""
    _, grid = _layer_grid()
    portrayal = {
        "sugar": {"colormap": "viridis", "alpha": 0.4, "colorbar": False},
        "flag": {"colormap": "reds"},
        "missing": {"color": "red"},
    }
    base, cbar = chart_property_layers(grid, portrayal, CHART, CHART)
    assert cbar is None
    spec = base.to_dict()
    assert len(spec["layer"]) == 2
    flag_chart, sugar_chart = spec["layer"]
    assert sugar_chart["mark"] == {"type": "rect", "opacity": 0.4}
    assert sugar_chart["encoding"]["color"]["scale"] == {
        "scheme": "viridis",
        "domain": [0.0, 11.0],
    }
    assert sugar_chart["encoding"]["color"]["legend"] is None
    assert flag_chart["encoding"]["color"]["legend"] == {"title": "flag"}


def test_two_colorbars_are_stacked():
    """Two colorbars are stacked."""
    _, grid = _layer_grid()
    _, cbar = chart_property_layers(
        grid, {"sugar": {"color": "red"}, "flag": {"color": "blue"}}, CHART, CHART
    )
    assert isinstance(cbar, alt.VConcatChart)
    assert len(cbar.vconcat) == 2


def test_layer_without_color_or_colormap_is_rejected():
    """Layer without color or colormap is rejected."""
    _, grid = _layer_grid()
    with pytest.raises(ValueError, match="must include 'color' or 'colormap'"):
        chart_property_layers(grid, {"sugar": {"alpha": 1}}, CHART, CHART)


def test_portrayal_to_dict():
    """Portrayal to dict."""
    agent = SimpleNamespace(unique_id=3)
    style = AgentPortrayalStyle(color="red", size=None)
    assert _portrayal_to_dict(style, agent) == {"id": 3, "color": "red"}
    style = AgentPortrayalStyle(color=None, size=9)
    assert _portrayal_to_dict(style, agent) == {"id": 3, "size": 9}
    raw = {"color": "blue"}
    assert _portrayal_to_dict(raw, agent) is raw


def _populated_grid():
    model, grid = _grid()
    for coordinate in [(0, 0), (3, 2)]:
        agent = CellAgent(model)
        agent.cell = grid[coordinate]
    return model, grid


def test_get_agent_data_grid():
    """Get agent data grid."""
    _, grid = _populated_grid()
    data = _get_agent_data(grid, lambda a: {"color": "red", "wealth": 1.5})
    assert sorted((d["x"], d["y"]) for d in data) == [(0, 0), (3, 2)]
    assert all(d["color"] == "red" for d in data)


def test_get_agent_data_continuous_uses_agent_positions():
    """Get agent data continuous uses agent positions."""

    class LegacyAgent:
        unique_id = 1
        pos = (0.5, 1.5)

    space = SimpleNamespace(_agent_to_index={LegacyAgent(): 0})
    data = _get_agent_data_continuous_space(
        space, lambda a: AgentPortrayalStyle(color="k", size=None)
    )
    assert data == [{"id": 1, "color": "k", "x": 0.5, "y": 1.5}]


def test_draw_grid_continuous_space_places_agents_by_position():
    """The legacy Altair chart draws ContinuousSpace agents at their positions."""
    model = Model(rng=1)
    space = ContinuousSpace([[0, 10], [0, 5]], random=model.random)
    for position in ([1.0, 2.0], [7.5, 3.25]):
        ContinuousSpaceAgent(space, model).position = position
    spec = _draw_grid(space, lambda a: {"color": "red"}, None).to_dict()
    assert sorted((d["x"], d["y"]) for d in spec["data"]["values"]) == [
        (1.0, 2.0),
        (7.5, 3.25),
    ]
    assert spec["encoding"]["x"]["type"] == "quantitative"
    assert spec["encoding"]["x"]["scale"]["domain"] == [0, 10]
    assert spec["encoding"]["y"]["scale"]["domain"] == [0, 5]


def test_get_agent_data_unsupported_space():
    """Get agent data unsupported space."""
    with pytest.raises(NotImplementedError, match="not supported through altair"):
        _get_agent_data(object(), lambda a: {})


def test_tooltips_skip_drawn_channels():
    """Tooltips skip drawn channels."""
    tips = _tooltips(
        {"color": "r", "x": 1, "y": 2, "size": 3, "wealth": 2.0, "kind": "a"}
    )
    assert [t.to_dict() for t in tips] == [
        {"field": "wealth", "type": "quantitative"},
        {"field": "kind", "type": "nominal"},
    ]


def test_agent_encoding_channels():
    """Agent encoding channels."""
    _, grid = _grid()
    data = [{"color": "red", "size": 3}, {"color": "blue", "size": 4}]
    encoding = _agent_encoding(grid, data)
    assert encoding["x"].to_dict()["type"] == "ordinal"
    assert sorted(encoding["color"].to_dict()["scale"]["domain"]) == ["blue", "red"]
    assert encoding["size"].to_dict() == {"field": "size", "type": "quantitative"}
    continuous = ContinuousSpace([[0, 1], [0, 1]], random=Model(rng=1).random)
    encoding = _agent_encoding(continuous, [])
    assert encoding["x"].to_dict()["type"] == "quantitative"
    assert "color" not in encoding
    assert encoding["tooltip"] == []


def test_draw_grid_agents_only_autoscales_marker():
    """Draw grid agents only autoscales marker."""
    _, grid = _populated_grid()
    spec = _draw_grid(grid, lambda a: {"color": "red"}, None).to_dict()
    assert spec["mark"] == {"type": "point", "filled": True, "size": 30000 / 9}
    assert len(spec["data"]["values"]) == 2


def test_draw_grid_with_size_keeps_size_channel():
    """Draw grid with size keeps size channel."""
    _, grid = _populated_grid()
    spec = _draw_grid(grid, lambda a: {"size": 5}, None).to_dict()
    assert "size" not in spec["mark"]
    assert spec["encoding"]["size"]["field"] == "size"


def test_draw_grid_with_property_layers_and_colorbar():
    """Draw grid with property layers and colorbar."""
    _, grid = _layer_grid()
    agent = CellAgent(Model(rng=1))
    agent.cell = grid[(1, 1)]
    chart = _draw_grid(grid, lambda a: {"color": "red"}, {"sugar": {"color": "red"}})
    spec = chart.to_dict()
    layered, cbar = spec["vconcat"]
    assert len(layered["layer"]) == 2
    assert len(cbar["layer"]) == 4
    assert spec["config"]["view"]["stroke"] is None


def test_draw_grid_with_colormap_layer_only():
    """Draw grid with colormap layer only."""
    _, grid = _layer_grid()
    chart = _draw_grid(grid, lambda a: {}, {"sugar": {"colormap": "blues"}})
    assert isinstance(chart, alt.LayerChart)
