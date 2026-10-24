"""Tests for the portrayal API shared by the Matplotlib and Altair backends and Studio."""

import importlib

import pytest

from modelly.examples import WolfSheep
from modelly.viz.altair import agent_data as altair_data
from modelly.viz.mpl import agent_data as mpl_data
from modelly.viz.palettes import OKABE_ITO, TOL_BRIGHT
from modelly.viz.render.portrayal import (
    AgentPortrayalStyle,
    ClassColours,
    dict_to_style,
    style_defaults,
    warn_dict_portrayal,
)


def test_both_backends_share_the_defaults():
    """The backends' default helpers are the shared one."""
    assert mpl_data.portrayal_style_defaults() == style_defaults()
    assert altair_data.style_defaults() == style_defaults()
    assert style_defaults()["color"] == AgentPortrayalStyle.color


def test_dict_to_style_reports_unused_keys():
    """A legacy dict becomes a style; keys it cannot use are returned."""
    style, ignored = dict_to_style(
        {"color": "red", "shape": "x"}, (1, 2), style_defaults()
    )
    assert (style.x, style.y, style.color) == (1, 2, "red")
    assert ignored == ["shape"]


def test_backend_wrappers_warn_about_unused_keys():
    """Both backends still warn, with their own messages, as before."""
    fields = style_defaults()
    with pytest.warns(UserWarning, match="were ignored: shape"):
        mpl_data.style_from_dict({"shape": 1}, (0, 0), fields, "were ignored: ")
    with pytest.warns(UserWarning, match="ignored from dict portrayal: shape"):
        altair_data.style_from_dict({"shape": 1}, (0, 0), fields)


def test_dict_portrayal_is_deprecated():
    """Returning a dict warns FutureWarning, from both backends."""
    with pytest.warns(FutureWarning, match="deprecated"):
        warn_dict_portrayal()
    with pytest.warns(FutureWarning, match="deprecated"):
        altair_data.warn_dict_portrayal()


def test_class_colours_gives_one_colour_per_class():
    """Each agent class gets the next palette colour, the same one every time."""
    model = WolfSheep()
    portrayal = ClassColours()
    seen = {type(a).__name__: portrayal(a).color for a in model.agents}
    assert sorted(seen.values()) == sorted(OKABE_ITO[: len(seen)])
    wolf = next(a for a in model.agents if type(a).__name__ == "Wolf")
    assert portrayal(wolf).color == seen["Wolf"]


def test_class_colours_cycles_a_custom_palette():
    """A short palette wraps around."""
    portrayal = ClassColours(palette=TOL_BRIGHT[:1], size=7)
    model = WolfSheep()
    styles = {portrayal(a).color for a in model.agents}
    assert styles == {TOL_BRIGHT[0]}
    assert portrayal(next(iter(model.agents))).size == 7


def test_render_package_imports_backends_lazily():
    """``modelly.viz.render`` still exports the backends, imported on first use."""
    render = importlib.import_module("modelly.viz.render")
    assert render.MatplotlibBackend.__name__ == "MatplotlibBackend"
    assert render.AltairBackend.__name__ == "AltairBackend"
    with pytest.raises(AttributeError):
        render.NoSuchBackend  # noqa: B018
