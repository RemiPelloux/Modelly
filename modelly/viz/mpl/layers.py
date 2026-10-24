"""Draw property layers with matplotlib.

``draw_property_layers`` is the functional API; the layer style and drawing
helpers are shared with ``MatplotlibBackend.draw_property_layer``.
"""

import itertools
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from matplotlib.cm import ScalarMappable
from matplotlib.collections import PolyCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize, to_rgba

import modelly
from modelly.space import OrthogonalMooreGrid, OrthogonalVonNeumannGrid

OrthogonalGrid = OrthogonalMooreGrid | OrthogonalVonNeumannGrid
HexGrid = modelly.space.HexGrid

TRANSPARENT = (0, 0, 0, 0)
RGBA_CHANNELS = 4
ALPHA_CHANNEL = 3
# Rows of a pointy-top hex grid are 1.5 hexagon radii apart.
ROW_SPACING_FACTOR = 1.5


@dataclass(frozen=True)
class LayerStyle:
    """The resolved colours and value range of one property layer."""

    name: str
    cmap: Any
    rgba_color: tuple | None
    alpha: float
    vmin: Any
    vmax: Any


def layer_style(layer_name, portrayal, limits, missing_color_msg):
    """Resolve a PropertyLayerStyle into a LayerStyle with the (vmin, vmax) limits.

    Raises:
        ValueError: with ``missing_color_msg`` if neither color nor colormap is set.
    """
    color, colormap, alpha = portrayal.color, portrayal.colormap, portrayal.alpha
    rgba_color = None
    if color:
        rgba_color = to_rgba(color)
        cmap = LinearSegmentedColormap.from_list(
            layer_name, [TRANSPARENT, (*rgba_color[:ALPHA_CHANNEL], alpha)]
        )
    elif colormap:
        cmap = colormap
        if isinstance(cmap, list):
            cmap = LinearSegmentedColormap.from_list(layer_name, cmap)
        elif isinstance(cmap, str):
            cmap = plt.get_cmap(cmap)
    else:
        raise ValueError(missing_color_msg)
    vmin, vmax = limits
    return LayerStyle(layer_name, cmap, rgba_color, alpha, vmin, vmax)


def draw_orthogonal_layer(ax, data, style: LayerStyle):
    """Draw a layer of an orthogonal grid as an image."""
    if style.rgba_color is not None:
        data = data.T
        normalized_data = (data - style.vmin) / (style.vmax - style.vmin)
        rgba_data = np.full((*data.shape, RGBA_CHANNELS), style.rgba_color)
        rgba_data[..., ALPHA_CHANNEL] *= normalized_data * style.alpha
        rgba_data = np.clip(rgba_data, 0, 1)
        ax.imshow(rgba_data, origin="lower")
    else:
        ax.imshow(
            data.T,
            cmap=style.cmap,
            alpha=style.alpha,
            vmin=style.vmin,
            vmax=style.vmax,
            origin="lower",
        )


def draw_hex_layer(ax, hexagons, colors, style: LayerStyle):
    """Draw a layer of a hex grid as one filled polygon per hexagon."""
    norm = Normalize(vmin=style.vmin, vmax=style.vmax)
    if style.rgba_color is not None:
        normalized_colors = np.clip(norm(colors), 0, 1)
        rgba_colors = np.full((len(colors), RGBA_CHANNELS), style.rgba_color)
        rgba_colors[:, ALPHA_CHANNEL] = normalized_colors * style.alpha
    else:
        rgba_colors = style.cmap(norm(colors))
        rgba_colors[..., ALPHA_CHANNEL] *= style.alpha
    collection = PolyCollection(hexagons, facecolors=rgba_colors, zorder=-1)
    ax.add_collection(collection)


def add_layer_colorbar(ax, style: LayerStyle):
    """Add a colorbar for the layer and return it."""
    norm = Normalize(vmin=style.vmin, vmax=style.vmax)
    sm = ScalarMappable(norm=norm, cmap=style.cmap)
    sm.set_array([])
    return plt.colorbar(sm, ax=ax, label=style.name)


@lru_cache(maxsize=1024, typed=True)
def _get_hexmesh(
    width: int, height: int, size: float = 1.0
) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Generate hexagon vertices for the mesh.

    Returns one entry per hexagon, each being the tuple of its six vertex
    coordinates. The result is cached and returned as nested immutable tuples so
    the shared cached object cannot be mutated by callers (which would poison the
    cache for every other same-sized grid).
    """
    x_spacing = np.sqrt(3) * size
    y_spacing = ROW_SPACING_FACTOR * size
    hexagons = []

    for row, col in itertools.product(range(height), range(width)):
        # Calculate center position with offset for even rows
        x = col * x_spacing + (row % 2 == 0) * (x_spacing / 2)
        y = row * y_spacing
        hexagons.append(_get_hex_vertices(x, y, size))

    return tuple(hexagons)


def _get_hex_vertices(
    center_x: float, center_y: float, size: float = 1.0
) -> tuple[tuple[float, float], ...]:
    """Get vertices for a hexagon centered at (center_x, center_y)."""
    vertices = (
        (center_x, center_y + size),  # top
        (center_x + size * np.sqrt(3) / 2, center_y + size / 2),  # top right
        (center_x + size * np.sqrt(3) / 2, center_y - size / 2),  # bottom right
        (center_x, center_y - size),  # bottom
        (center_x - size * np.sqrt(3) / 2, center_y - size / 2),  # bottom left
        (center_x - size * np.sqrt(3) / 2, center_y + size / 2),  # top left
    )
    return vertices


def draw_property_layers(
    space, property_layer_portrayal: dict[str, dict[str, Any]] | Callable, ax: Axes
):
    """Draw Property Layers on the given axes.

    Args:
        space: The space having the property_layer.
        property_layer_portrayal (Callable): A function that accepts a property layer object
            and returns either a `PropertyLayerStyle` object defining its visualization,
            or `None` to skip drawing this particular layer.
        ax (matplotlib.axes.Axes): The axes to draw on.

    """
    property_layers = space.property_layers
    callable_portrayal = _dict_portrayal_to_callable(property_layer_portrayal)

    for layer_name in property_layers:
        if layer_name == "empty":
            # Skipping empty layer, automatically generated
            continue

        layer = property_layers.get(layer_name, None)
        portrayal = callable_portrayal(layer_name)

        if portrayal is None:
            # Not visualizing layers that do not have a defined visual encoding.
            continue

        data = layer.astype(float) if layer.dtype == bool else layer
        _warn_if_shape_mismatch(space, layer_name, data)
        style = _space_layer_style(layer_name, portrayal, data)
        _draw_space_layer(ax, space, data, style)
        if portrayal.colorbar:
            add_layer_colorbar(ax, style)


def _dict_portrayal_to_callable(property_layer_portrayal):
    """Convert a legacy portrayal dict to a callable; return anything else as-is."""
    # Imported here: modelly.viz.render imports the backend, which imports this module
    from modelly.viz.render.portrayal import (  # noqa: PLC0415
        property_layer_dict_to_callable,
    )

    if isinstance(property_layer_portrayal, dict):
        return property_layer_dict_to_callable(property_layer_portrayal)
    return property_layer_portrayal


def _warn_if_shape_mismatch(space, layer_name, data):
    """Warn (and carry on) when the layer shape differs from the space."""
    if (space.width, space.height) != data.shape:
        warnings.warn(
            f"Layer {layer_name} dimensions ({data.shape}) do not match space dimensions ({space.width}, {space.height}).",
            UserWarning,
            stacklevel=3,  # the caller of draw_property_layers()
        )


def _space_layer_style(layer_name, portrayal, data):
    """Resolve the style; unset (or zero) vmin/vmax fall back to the data range."""
    vmin = portrayal.vmin if portrayal.vmin else np.min(data)
    vmax = portrayal.vmax if portrayal.vmax else np.max(data)
    return layer_style(
        layer_name,
        portrayal,
        (vmin, vmax),
        f"Property {layer_name} portrayal must include 'color' or 'colormap'.",
    )


def _draw_space_layer(ax, space, data, style: LayerStyle):
    """Draw one property layer of an orthogonal or hex grid."""
    if isinstance(space, OrthogonalGrid):
        draw_orthogonal_layer(ax, data, style)
    elif isinstance(space, HexGrid):
        width, height = data.shape
        draw_hex_layer(ax, _get_hexmesh(width, height), data.ravel(), style)
    else:
        raise NotImplementedError(
            f"Property visualization not implemented for {type(space)}."
        )
