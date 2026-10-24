"""Render the Altair and Matplotlib space/plot components without a browser."""

import warnings

import ipywidgets
import pytest
import solara

from modelly import Model
from modelly.data.collector import DataCollector
from modelly.space import CellAgent, OrthogonalMooreGrid
from modelly.viz import components as facade
from modelly.viz.altair import components as altair_components
from modelly.viz.altair.components import (
    PlotAltair,
    SpaceAltair,
    _measures_to_plot,
    make_altair_plot_component,
    make_altair_space,
    make_space_altair,
)
from modelly.viz.components import (
    AgentPortrayalStyle,
    PropertyLayerStyle,
    make_plot_component,
    make_space_component,
)
from modelly.viz.mpl import components as mpl_components
from modelly.viz.mpl.components import (
    PlotMatplotlib,
    SpaceMatplotlib,
    make_mpl_plot_component,
    make_mpl_space_component,
    make_plot_measure,
    make_space_matplotlib,
)


class GridModel(Model):
    """Two agents on a 5x5 grid, a sugar layer and a two-measure collector."""

    def __init__(self, attribute="grid"):
        """Create the instance."""
        super().__init__(rng=3)
        grid = OrthogonalMooreGrid((5, 5), random=self.random)
        grid.create_property_layer("sugar", default_value=1.0)
        setattr(self, attribute, grid)
        for coordinate in [(1, 1), (3, 4)]:
            agent = CellAgent(self)
            agent.cell = grid[coordinate]
        self.wealth, self.count = 1, 2
        self.datacollector = DataCollector(
            model_reporters={"Wealth": "wealth", "Count": "count"}
        )
        for step in range(3):
            self.wealth += step
            self.datacollector.collect(self)


def _figures(rc, cls):
    return rc.find(cls).widgets


def _altair_spec(rc):
    widget = rc.find(solara.widgets.VegaLite).widget
    return widget.spec


@pytest.mark.parametrize("attribute", ["grid", "space"])
def test_space_altair_draws_agents(attribute):
    """Space altair draws agents."""
    model = GridModel(attribute)
    seen = []

    def post(chart):
        seen.append(chart)
        return chart.properties(title="post-processed")

    _, rc = solara.render(
        SpaceAltair(model, lambda a: {"color": "red"}, post_process=post),
        handle_error=False,
    )
    assert len(seen) == 1
    spec = _altair_spec(rc)
    assert spec["title"] == "post-processed"
    assert len(spec["data"]["values"]) == 2


def test_make_altair_space_default_portrayal_and_layers():
    """Make altair space default portrayal and layers."""
    model = GridModel()
    make = make_altair_space(None, {"sugar": {"colormap": "viridis"}})
    _, rc = solara.render(make(model), handle_error=False)
    spec = _altair_spec(rc)
    assert len(spec["layer"]) == 2


def test_make_space_altair_is_deprecated_alias():
    """Make space altair is deprecated alias."""
    with pytest.warns(FutureWarning, match="make_altair_space"):
        make = make_space_altair(lambda a: {"color": "blue"})
    _, rc = solara.render(make(GridModel()), handle_error=False)
    assert _altair_spec(rc)["mark"]["type"] == "point"


@pytest.mark.parametrize(
    ("measure", "expected", "title"),
    [
        ("Wealth", ["Wealth"], "Wealth"),
        (["Wealth", "Count"], ["Wealth", "Count"], "Value"),
        (("Count",), ["Count"], "Value"),
        ({"Wealth": "red", "Count": "blue"}, ["Wealth", "Count"], "Value"),
    ],
)
def test_measures_to_plot(measure, expected, title):
    """Measures to plot."""
    assert _measures_to_plot(measure) == (expected, title)


def test_plot_altair_single_measure_with_post_process():
    """Plot altair single measure with post process."""
    model = GridModel()
    seen = []

    def post(chart):
        seen.append(chart)
        return chart

    plot, page = make_altair_plot_component("Wealth", post_process=post, page=2)
    assert page == 2
    _, rc = solara.render(plot(model), handle_error=False)
    spec = _altair_spec(rc)
    assert len(seen) == 1
    assert spec["encoding"]["y"]["axis"]["title"] == "Wealth"
    values = next(iter(spec["datasets"].values()))
    assert [row["Value"] for row in values] == [1, 2, 4]
    assert spec["encoding"]["color"]["field"] == "Measure"


def test_plot_altair_dict_measure_uses_given_colors():
    """Plot altair dict measure uses given colors."""
    model = GridModel()
    _, rc = solara.render(
        PlotAltair(model, {"Wealth": "red", "Count": "blue"}, grid=True),
        handle_error=False,
    )
    spec = _altair_spec(rc)
    scale = spec["encoding"]["color"]["scale"]
    assert scale == {"domain": ["Wealth", "Count"], "range": ["red", "blue"]}
    assert spec["encoding"]["x"]["axis"]["grid"] is True


def _mpl_axes(rc):
    figure = rc.find(ipywidgets.Image).widget
    assert figure.value  # the PNG bytes were rendered
    return figure


@pytest.mark.parametrize("attribute", ["grid", "space"])
def test_space_matplotlib_renders_and_post_processes(attribute):
    """Space matplotlib renders and post processes."""
    model = GridModel(attribute)
    seen = []
    _, rc = solara.render(
        SpaceMatplotlib(
            model,
            lambda a: AgentPortrayalStyle(color="red"),
            lambda layer: PropertyLayerStyle(colormap="viridis", colorbar=False),
            post_process=seen.append,
        ),
        handle_error=False,
    )
    _mpl_axes(rc)
    [ax] = seen
    assert len(ax.collections) >= 1
    assert len(ax.images) == 1


def test_make_mpl_space_component_default_portrayal():
    """Make mpl space component default portrayal."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        make = make_mpl_space_component()
        _, rc = solara.render(make(GridModel()), handle_error=False)
    _mpl_axes(rc)


def test_make_space_matplotlib_is_deprecated_alias():
    """Make space matplotlib is deprecated alias."""
    with pytest.warns(FutureWarning, match="make_mpl_space_component"):
        make = make_space_matplotlib(lambda a: AgentPortrayalStyle())
    assert callable(make)


@pytest.mark.parametrize(
    ("measure", "lines", "legend"),
    [
        ("Wealth", 1, False),
        (["Wealth", "Count"], 2, True),
        ({"Wealth": "red", "Count": "blue"}, 2, True),
    ],
)
def test_plot_matplotlib_measures(measure, lines, legend):
    """Plot matplotlib measures."""
    seen = []
    _, rc = solara.render(
        PlotMatplotlib(GridModel(), measure, post_process=seen.append),
        handle_error=False,
    )
    _mpl_axes(rc)
    [ax] = seen
    assert len(ax.lines) == lines
    assert (ax.get_legend() is not None) is legend
    if isinstance(measure, str):
        assert ax.get_ylabel() == "Wealth"
        assert list(ax.lines[0].get_ydata()) == [1, 2, 4]
    if isinstance(measure, dict):
        assert ax.lines[0].get_color() == "red"


def test_make_mpl_plot_component_and_alias():
    """Make mpl plot component and alias."""
    plot, page = make_mpl_plot_component("Count", page=1, save_format="svg")
    assert page == 1
    _, rc = solara.render(plot(GridModel()), handle_error=False)
    assert rc.find(ipywidgets.Image).widget.format == "svg+xml"
    with pytest.warns(FutureWarning, match="make_mpl_plot_component"):
        plot, page = make_plot_measure("Count")
    assert page == 0


def test_facade_space_component_dispatches_on_backend(monkeypatch):
    """Facade space component dispatches on backend."""
    calls = []
    monkeypatch.setattr(
        facade, "make_mpl_space_component", lambda *a, **k: calls.append(("mpl", a, k))
    )
    monkeypatch.setattr(
        facade, "make_altair_space", lambda *a, **k: calls.append(("altair", a, k))
    )
    make_space_component("p", "layers", "post", backend="matplotlib", s=3)
    make_space_component("p", backend="altair")
    assert calls == [
        ("mpl", ("p", "layers", "post"), {"s": 3}),
        ("altair", ("p", None, None), {}),
    ]
    with pytest.raises(ValueError, match="unknown backend bokeh"):
        make_space_component(backend="bokeh")


def test_facade_plot_component_dispatches_on_backend():
    """Facade plot component dispatches on backend."""
    plot, page = make_plot_component("Wealth", backend="matplotlib", page=3)
    assert page == 3
    assert plot.__name__ == "MakePlotMatplotlib"
    plot, page = make_plot_component("Wealth", backend="altair", grid=True)
    assert plot.__name__ == "MakePlotAltair"
    _, rc = solara.render(plot(GridModel()), handle_error=False)
    assert _altair_spec(rc)["encoding"]["x"]["axis"]["grid"] is True
    with pytest.raises(ValueError, match="unknown backend"):
        make_plot_component("Wealth", backend="plotly")


def test_modules_export_public_names():
    """Modules export public names."""
    assert "SpaceAltair" in altair_components.__all__
    assert callable(mpl_components.make_mpl_space_component)
