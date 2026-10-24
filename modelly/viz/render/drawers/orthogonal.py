"""Drawer for orthogonal grid spaces."""

import altair as alt
import numpy as np
import pandas as pd

from modelly.viz.render.drawers.base import (
    MARKER_SPAN_POINTS,
    BaseSpaceDrawer,
    OrthogonalGrid,
    axes_with_figure_kwargs,
    chart_properties,
)

# Cell centres sit on integers, so cell edges are half a unit away.
HALF_CELL = 0.5


class OrthogonalSpaceDrawer(BaseSpaceDrawer):
    """Drawer for orthogonal grid spaces (SingleGrid, MultiGrid, Moore, VonNeumann)."""

    def __init__(self, space: OrthogonalGrid):
        """Initialize the orthogonal space drawer.

        Args:
            space: The orthogonal grid space to draw
        """
        super().__init__(space)
        self.s_default = (
            MARKER_SPAN_POINTS / max(self.space.width, self.space.height)
        ) ** 2

        # Parameters for visualization limits
        self.viz_xmin = -HALF_CELL
        self.viz_xmax = self.space.width - HALF_CELL
        self.viz_ymin = -HALF_CELL
        self.viz_ymax = self.space.height - HALF_CELL

    def draw_matplotlib(self, ax=None, **draw_space_kwargs):
        """Draw the orthogonal grid using matplotlib.

        Args:
            ax: Matplotlib axes object to draw on
            **draw_space_kwargs: Additional keyword arguments for styling.

        Examples:
                figsize=(10, 10), color="blue", linewidth=2.

        Returns:
            The modified axes object
        """
        ax = axes_with_figure_kwargs(ax, draw_space_kwargs)

        # gridline styling kwargs
        line_kwargs = {
            "color": "gray",
            "linestyle": ":",
            "linewidth": 1,
            "alpha": 1,
        }
        line_kwargs.update(draw_space_kwargs)

        ax.set_xlim(self.viz_xmin, self.viz_xmax)
        ax.set_ylim(self.viz_ymin, self.viz_ymax)

        # Draw grid lines
        for x in np.arange(-HALF_CELL, self.space.width, 1):
            ax.axvline(x, **line_kwargs)
        for y in np.arange(-HALF_CELL, self.space.height, 1):
            ax.axhline(y, **line_kwargs)

        return ax

    def draw_altair(self, chart_width=450, chart_height=350, **draw_chart_kwargs):
        """Draw the orthogonal grid using Altair.

        Args:
            chart_width: Width for the shown chart
            chart_height: Height for the shown chart
            **draw_chart_kwargs: Additional keyword arguments for styling the chart.

        Examples:
                width=500, height=500, title="Grid".

        Returns:
            Altair chart object
        """
        # for axis and grid styling
        axis_kwargs = {
            "xlabel": draw_chart_kwargs.pop("xlabel", "X"),
            "ylabel": draw_chart_kwargs.pop("ylabel", "Y"),
            "grid_color": draw_chart_kwargs.pop("grid_color", "lightgray"),
            "grid_dash": draw_chart_kwargs.pop("grid_dash", [2, 2]),
            "grid_width": draw_chart_kwargs.pop("grid_width", 1),
            "grid_opacity": draw_chart_kwargs.pop("grid_opacity", 1),
        }
        chart_props = chart_properties(chart_width, chart_height, draw_chart_kwargs)

        x_domain = [self.viz_xmin, self.viz_xmax]
        y_domain = [self.viz_ymin, self.viz_ymax]
        return (
            alt.Chart(pd.DataFrame([{}]))
            .mark_point(opacity=0)
            .encode(
                x=alt.X(
                    "X:Q", **_gridded_axis(axis_kwargs["xlabel"], x_domain, axis_kwargs)
                ),
                y=alt.Y(
                    "Y:Q", **_gridded_axis(axis_kwargs["ylabel"], y_domain, axis_kwargs)
                ),
            )
            .properties(**chart_props)
        )


def _gridded_axis(title, domain, axis_kwargs):
    """Return the title, scale and gridded axis for one Altair position channel."""
    return {
        "title": title,
        "scale": alt.Scale(domain=domain, nice=False),
        "axis": alt.Axis(
            grid=True,
            gridColor=axis_kwargs["grid_color"],
            gridDash=axis_kwargs["grid_dash"],
            gridWidth=axis_kwargs["grid_width"],
            gridOpacity=axis_kwargs["grid_opacity"],
        ),
    }
