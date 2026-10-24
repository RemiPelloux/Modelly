"""Plot collected agent data as scatter markers or image markers.

``_scatter`` is the functional API's plotter; the marker helpers are shared with
``MatplotlibBackend.draw_agents``.
"""

import os
from dataclasses import dataclass
from typing import Any

import numpy as np
from matplotlib.axes import Axes
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from PIL import Image

CORRECTION_FACTOR_MARKER_ZOOM = 0.6
DEFAULT_MARKER_SIZE = 50


@dataclass(frozen=True)
class ScatterData:
    """Per-agent columns to plot, the other scatter arguments and the plot kwargs."""

    loc_x: np.ndarray
    loc_y: np.ndarray
    marker: np.ndarray
    zorder: np.ndarray
    alpha: np.ndarray
    size: np.ndarray
    scatter_args: dict[str, Any]
    kwargs: dict[str, Any]


def validate_edge_arguments(arguments, kwargs):
    """Drop unset edge arguments; reject ones set both per agent and via kwargs.

    We check if edgecolor and linewidth are specified at the agent level, if not,
    we remove them from the arguments dict and fall back to the default value in
    ax.scatter / use what is passed via **kwargs.
    """
    for entry in ["edgecolors", "linewidths"]:
        if len(arguments[entry]) == 0:
            arguments.pop(entry)
        elif entry in kwargs:
            raise ValueError(
                f"{entry} is specified in agent portrayal and via plotting kwargs, "
                "you can only use one or the other"
            )


def is_image_marker(mark):
    """Return whether the marker is the path of an image file."""
    return isinstance(mark, str | os.PathLike) and os.path.isfile(mark)


def zoom_factor(ax, img, correction):
    """Return the zoom that scales the image to one data unit, times ``correction``."""
    ax.get_figure().canvas.draw()
    bbox = ax.get_window_extent().transformed(
        ax.get_figure().dpi_scale_trans.inverted()
    )  # in inches
    width, height = (
        bbox.width * ax.get_figure().dpi,
        bbox.height * ax.get_figure().dpi,
    )  # in pixel

    xr = ax.get_xlim()
    yr = ax.get_ylim()

    x_pixel_per_data = width / (xr[1] - xr[0])
    y_pixel_per_data = height / (yr[1] - yr[0])

    zoom_x = (x_pixel_per_data / img.width) * correction
    zoom_y = (y_pixel_per_data / img.height) * correction

    return min(zoom_x, zoom_y)


def add_image_artists(ax, im, mask, data: ScatterData):
    """Add the image at every masked agent, grouped by zorder then alpha."""
    for z_order in np.unique(data.zorder[mask]):
        for m_alpha in np.unique(data.alpha[mask]):
            final_mask = (data.zorder == z_order) & (data.alpha == m_alpha) & mask
            for x, y in zip(data.loc_x[final_mask], data.loc_y[final_mask]):
                ab = AnnotationBbox(
                    im,
                    (x, y),
                    frameon=False,
                    pad=0.0,
                    zorder=z_order,
                    **data.kwargs,
                )
                ax.add_artist(ab)


def scatter_by_zorder(ax, mark, mask_marker, data: ScatterData):
    """Scatter the agents with this marker, one call per zorder."""
    for z_order in np.unique(data.zorder[mask_marker]):
        zorder_mask = (data.zorder == z_order) & mask_marker
        ax.scatter(
            data.loc_x[zorder_mask],
            data.loc_y[zorder_mask],
            marker=mark,
            zorder=z_order,
            **{k: v[zorder_mask] for k, v in data.scatter_args.items()},
            **data.kwargs,
        )


def _get_zoom_factor(ax, img):
    """Return the image zoom for the functional API's image markers."""
    return zoom_factor(ax, img, CORRECTION_FACTOR_MARKER_ZOOM)


def _scatter(ax: Axes, arguments, **kwargs):
    """Helper function for plotting the agents.

    Args:
        ax: a Matplotlib Axes instance
        arguments: the agents specific arguments for plotting
        kwargs: additional keyword arguments for ax.scatter

    """
    loc = arguments.pop("loc")
    marker = arguments.pop("marker")
    data = ScatterData(
        loc_x=loc[:, 0],
        loc_y=loc[:, 1],
        marker=marker,
        zorder=arguments.pop("zorder"),
        alpha=arguments.pop("alpha"),
        size=arguments.pop("s"),
        scatter_args=arguments,
        kwargs=kwargs,
    )
    validate_edge_arguments(arguments, kwargs)

    ax.get_figure().canvas.draw()
    for mark in set(marker):
        if is_image_marker(mark):
            _scatter_image(ax, mark, data)
        else:
            # ordinary markers
            scatter_by_zorder(ax, mark, [m == mark for m in list(marker)], data)


def _scatter_image(ax, mark, data: ScatterData):
    """Draw the agents whose marker is this image, one image per marker size."""
    for m_size in np.unique(data.size):
        image = Image.open(mark)
        im = OffsetImage(
            image,
            zoom=_get_zoom_factor(ax, image) * m_size / DEFAULT_MARKER_SIZE,
        )
        im.image.axes = ax

        mask_marker = [m == mark for m in list(data.marker)] & (m_size == data.size)
        add_image_artists(ax, im, mask_marker, data)
