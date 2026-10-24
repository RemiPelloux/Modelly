"""Tests for drawing property layers with matplotlib (orthogonal and hex grids)."""

import numpy as np
import pytest
from matplotlib.collections import PolyCollection
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure

from modelly import Model
from modelly.space import HexGrid, OrthogonalMooreGrid
from modelly.space.continuous import ContinuousSpace
from modelly.viz.components import PropertyLayerStyle
from modelly.viz.mpl.layers import (
    draw_property_layers,
    layer_style,
)


def _ax():
    return Figure().add_subplot()


def _grid(cls=OrthogonalMooreGrid, shape=(4, 3)):
    grid = cls(shape, random=Model(rng=5).random)
    grid.create_property_layer("heat", default_value=0.0)
    grid.property_layers["heat"][:] = np.arange(12, dtype=float).reshape(shape)
    return grid


def test_layer_style_from_list_colormap():
    """Layer style from list colormap."""
    style = layer_style(
        "heat", PropertyLayerStyle(colormap=["white", "red"]), (0, 1), "unused"
    )
    assert isinstance(style.cmap, LinearSegmentedColormap)
    assert style.cmap.name == "heat"
    assert style.rgba_color is None


def test_layer_style_keeps_colormap_objects():
    """Layer style keeps colormap objects."""
    cmap = LinearSegmentedColormap.from_list("mine", ["k", "w"])
    style = layer_style("heat", PropertyLayerStyle(colormap=cmap), (2, 3), "unused")
    assert style.cmap is cmap
    assert (style.vmin, style.vmax) == (2, 3)


def test_layer_style_requires_color_or_colormap():
    """Layer style requires color or colormap."""
    portrayal = PropertyLayerStyle(color="red")
    portrayal.color = None
    with pytest.raises(ValueError, match="custom message"):
        layer_style("heat", portrayal, (0, 1), "custom message")


def test_orthogonal_colormap_layer_with_colorbar():
    """Orthogonal colormap layer with colorbar."""
    ax = _ax()
    draw_property_layers(
        _grid(), lambda name: PropertyLayerStyle(colormap="viridis"), ax
    )
    [image] = ax.images
    assert image.get_array().shape == (3, 4)  # transposed for imshow
    assert image.get_clim() == (0.0, 11.0)
    assert len(ax.figure.axes) == 2  # the colorbar axes


def test_orthogonal_color_layer_scales_alpha():
    """Orthogonal color layer scales alpha."""
    ax = _ax()
    draw_property_layers(
        _grid(),
        lambda name: PropertyLayerStyle(color="red", alpha=0.5, colorbar=False),
        ax,
    )
    rgba = ax.images[0].get_array()
    assert rgba.shape == (3, 4, 4)
    assert rgba[0, 0, 3] == 0.0
    assert rgba[-1, -1, 3] == pytest.approx(0.5)
    assert len(ax.figure.axes) == 1


@pytest.mark.parametrize(
    "portrayal",
    [
        PropertyLayerStyle(color="blue", alpha=0.6, colorbar=False),
        PropertyLayerStyle(colormap="plasma", alpha=0.5, colorbar=False),
    ],
)
def test_hex_layer_draws_one_polygon_per_cell(portrayal):
    """Hex layer draws one polygon per cell."""
    ax = _ax()
    draw_property_layers(_grid(HexGrid), lambda name: portrayal, ax)
    [collection] = [c for c in ax.collections if isinstance(c, PolyCollection)]
    assert len(collection.get_paths()) == 12
    alphas = collection.get_facecolors()[:, 3]
    if portrayal.color:
        assert alphas.min() == 0.0
        assert alphas.max() == pytest.approx(0.6)
    else:
        assert np.allclose(alphas, 0.5)


def test_layers_without_portrayal_are_skipped():
    """Layers without portrayal are skipped."""
    ax = _ax()
    draw_property_layers(_grid(), lambda name: None, ax)
    assert len(ax.images) == 0


def test_bool_layers_and_legacy_dict_portrayal():
    """Bool layers and legacy dict portrayal."""
    grid = _grid()
    grid.create_property_layer("wet", default_value=False, dtype=bool)
    grid.property_layers["wet"][1, 1] = True
    ax = _ax()
    with pytest.warns(FutureWarning, match="property_layer_portrayal dict"):
        draw_property_layers(
            grid, {"wet": {"colormap": "Blues", "colorbar": False}}, ax
        )
    [image] = ax.images
    assert image.get_clim() == (0.0, 1.0)


def test_shape_mismatch_warns():
    """Shape mismatch warns."""

    class FakeSpace:
        width, height = 4, 3

    space = FakeSpace()
    space.property_layers = {"heat": np.zeros((2, 2))}
    with (
        pytest.raises(NotImplementedError, match="Property visualization"),
        pytest.warns(UserWarning, match="do not match space dimensions"),
    ):
        draw_property_layers(
            space, lambda name: PropertyLayerStyle(colormap="viridis"), _ax()
        )


def test_unsupported_space_raises():
    """Unsupported space raises."""
    space = ContinuousSpace([[0, 4], [0, 3]], random=Model(rng=1).random)
    space.property_layers = {"heat": np.zeros((4, 3))}
    with pytest.raises(NotImplementedError, match="not implemented"):
        draw_property_layers(
            space, lambda name: PropertyLayerStyle(colormap="viridis"), _ax()
        )
