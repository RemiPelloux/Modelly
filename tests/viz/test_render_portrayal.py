"""Tests for portrayal styles, legacy layer dicts and the Altair agent columns."""

import numpy as np
import pytest

from modelly.viz.altair.agent_data import (
    style_columns,
    style_defaults,
    style_from_dict,
    to_arrays,
    unsupported_marker,
)
from modelly.viz.render.portrayal import (
    AgentPortrayalStyle,
    PropertyLayerStyle,
    as_property_layer_callable,
    property_layer_dict_to_callable,
)


def test_agent_style_update_and_unknown_field():
    """Agent style update and unknown field."""
    style = AgentPortrayalStyle()
    style.update(("color", "red"), ("size", 30))
    assert (style.color, style.size) == ("red", 30)
    with pytest.raises(AttributeError, match="no attribute 'bogus'"):
        style.update(("bogus", 1))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"color": -1}, "non-negative"), ({"size": -2.5}, "non-negative number")],
)
def test_agent_style_rejects_negative_values(kwargs, message):
    """Agent style rejects negative values."""
    with pytest.raises(ValueError, match=message):
        AgentPortrayalStyle(**kwargs)


def test_layer_style_needs_exactly_one_color_source():
    """Layer style needs exactly one color source."""
    with pytest.raises(ValueError, match="not both"):
        PropertyLayerStyle(color="red", colormap="viridis")
    with pytest.raises(ValueError, match="Specify one of"):
        PropertyLayerStyle()


def test_layer_dict_to_callable_converts_and_skips():
    """Layer dict to callable converts and skips."""
    to_style = property_layer_dict_to_callable(
        {
            "heat": {
                "color": "red",
                "alpha": 0.3,
                "vmin": 1,
                "vmax": 9,
                "colorbar": False,
            }
        }
    )
    with pytest.warns(FutureWarning, match="dict is deprecated"):
        style = to_style("heat")
    assert style == PropertyLayerStyle(
        color="red", alpha=0.3, vmin=1, vmax=9, colorbar=False
    )
    with pytest.warns(FutureWarning):
        assert to_style("other") is None


def test_layer_dict_defaults():
    """Layer dict defaults."""
    to_style = property_layer_dict_to_callable({"heat": {"colormap": "viridis"}})
    with pytest.warns(FutureWarning):
        style = to_style("heat")
    assert style.alpha == PropertyLayerStyle.alpha
    assert style.colorbar is True


def test_as_property_layer_callable():
    """As property layer callable."""
    style = PropertyLayerStyle(colormap="viridis")
    assert as_property_layer_callable(style)("any layer") is style

    def portrayal(layer):
        return style

    assert as_property_layer_callable(portrayal) is portrayal
    converted = as_property_layer_callable({"heat": {"color": "blue"}})
    with pytest.warns(FutureWarning):
        assert converted("heat").color == "blue"


def test_style_from_dict_warns_about_ignored_keys():
    """Style from dict warns about ignored keys."""
    defaults = style_defaults()
    with pytest.warns(UserWarning, match="ignored from dict portrayal: shape, label"):
        style = style_from_dict(
            {"color": "red", "shape": "o", "label": "x"}, (1, 2), defaults
        )
    assert (style.x, style.y, style.color) == (1, 2, "red")
    assert style.size == defaults["size"]


def test_unsupported_marker_falls_back_to_circle():
    """Unsupported marker falls back to circle."""
    with pytest.warns(UserWarning, match="Marker 'None' is not supported"):
        assert unsupported_marker(None) == "circle"


def test_style_columns_fill_defaults_and_map_markers():
    """Style columns fill defaults and map markers."""
    defaults = style_defaults()
    styles = [
        AgentPortrayalStyle(x=0, y=1, marker="s", size=None, zorder=None),
        AgentPortrayalStyle(x=2, y=3, marker=None, alpha=None, tooltip={"id": 1}),
    ]
    columns = style_columns(styles, defaults, fallback_size=7)
    assert columns["loc"] == [(0, 1), (2, 3)]
    assert columns["size"] == [7, 50]
    assert columns["shape"] == ["square", "circle"]
    assert columns["order"] == [defaults["zorder"], 1]
    assert columns["opacity"] == [1.0, defaults["alpha"]]
    assert columns["tooltip"] == [None, {"id": 1}]


def test_style_columns_warn_when_no_marker_at_all():
    """Style columns warn when no marker at all."""
    defaults = {**style_defaults(), "marker": None}
    with pytest.warns(UserWarning, match="not supported in Altair"):
        columns = style_columns([AgentPortrayalStyle(marker=None)], defaults, 5)
    assert columns["shape"] == ["circle"]


def test_to_arrays_types():
    """To arrays types."""
    arrays = to_arrays(
        {"shape": ["circle", "square"], "size": [1, 2], "color": ["r", "b"]}
    )
    assert arrays["shape"].dtype == object
    assert arrays["size"].dtype == float
    assert arrays["color"].tolist() == ["r", "b"]
    assert isinstance(arrays["color"], np.ndarray)
