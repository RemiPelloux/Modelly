"""Drawer for hexagonal grid spaces."""

from itertools import pairwise

import altair as alt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection

from modelly.viz.render.drawers.base import (
    MARKER_SPAN_POINTS,
    BaseSpaceDrawer,
    HexGrid,
    axes_with_figure_kwargs,
    chart_properties,
    line_mark_kwargs,
)

# Rows of a pointy-top hex grid are 1.5 hexagon radii apart.
ROW_SPACING_FACTOR = 1.5
# Margin below/left of the first hexagon, in units of its padding.
LOWER_MARGIN_FACTOR = 1.8
# Decimals kept when de-duplicating shared hexagon edges.
EDGE_ROUNDING_DECIMALS = 6


class HexSpaceDrawer(BaseSpaceDrawer):
    """Drawer for hexagonal grid spaces."""

    def __init__(self, space: HexGrid):
        """Initialize the hexagonal space drawer.

        Args:
            space: The hexagonal grid space to draw
        """
        super().__init__(space)
        self.s_default = (
            MARKER_SPAN_POINTS / max(self.space.width, self.space.height)
        ) ** 2
        size = 1.0

        self.x_spacing = np.sqrt(3) * size
        self.y_spacing = ROW_SPACING_FACTOR * size

        x_max = self.space.width * self.x_spacing + (self.space.height % 2) * (
            self.x_spacing / 2
        )
        y_max = self.space.height * self.y_spacing

        x_padding = size * np.sqrt(3) / 2
        y_padding = size

        self.hexagons = self._get_hexmesh(size)

        # Parameters for visualization limits
        self.viz_xmin = -LOWER_MARGIN_FACTOR * x_padding
        self.viz_xmax = x_max
        self.viz_ymin = -LOWER_MARGIN_FACTOR * y_padding
        self.viz_ymax = y_max

    def _get_hexmesh(self, size: float = 1.0) -> list[list[tuple[float, float]]]:
        """Generate hexagon vertices for the mesh. Yields list of list of vertex coordinates for each hexagon."""
        hexagons = []
        for cell in self.space.all_cells:
            cx, cy = cell.position
            hexagons.append(_get_hex_vertices(cx, cy, size))

        return hexagons

    def _get_unique_edges(self):
        """Helper method to extract unique edges from all hexagons."""
        edges = set()
        # Generate edges for each hexagon
        for vertices in self.hexagons:
            # Edge logic, connecting each vertex to the next
            for v1, v2 in pairwise([*vertices, vertices[0]]):
                # Sort vertices to ensure consistent edge representation and avoid duplicates.
                edge = tuple(
                    sorted(
                        [
                            tuple(np.round(v1, EDGE_ROUNDING_DECIMALS)),
                            tuple(np.round(v2, EDGE_ROUNDING_DECIMALS)),
                        ]
                    )
                )
                edges.add(edge)
        return edges

    def draw_matplotlib(self, ax=None, **draw_space_kwargs):
        """Draw the hexagonal grid using matplotlib.

        Args:
            ax: Matplotlib axes object to draw on
            **draw_space_kwargs: Additional keyword arguments for styling.

        Examples:
                figsize=(8, 8), color="red", alpha=0.5.

        Returns:
            The modified axes object
        """
        ax = axes_with_figure_kwargs(ax, draw_space_kwargs)

        line_kwargs = {
            "color": "black",
            "linestyle": ":",
            "linewidth": 1,
            "alpha": 0.8,
        }
        line_kwargs.update(draw_space_kwargs)

        ax.set_xlim(self.viz_xmin, self.viz_xmax)
        ax.set_ylim(self.viz_ymin, self.viz_ymax)
        ax.set_aspect("equal", adjustable="box")

        edges = self._get_unique_edges()
        ax.add_collection(LineCollection(list(edges), **line_kwargs))
        return ax

    def draw_altair(self, chart_width=450, chart_height=350, **draw_chart_kwargs):
        """Draw the hexagonal grid using Altair.

        Args:
            chart_width: Width for the shown chart
            chart_height: Height for the shown chart
            **draw_chart_kwargs: Additional keyword arguments for styling the chart.

        Examples:
                * Line properties like color, strokeDash, strokeWidth, opacity.
                * Other kwargs (e.g., width, title) apply to the chart.

        Returns:
            Altair chart object representing the hexagonal grid.
        """
        mark_kwargs = line_mark_kwargs(draw_chart_kwargs)
        chart_props = chart_properties(chart_width, chart_height, draw_chart_kwargs)
        source = _edge_frame(self._get_unique_edges())

        return (
            alt.Chart(source)
            .mark_line(**mark_kwargs)
            .encode(
                x=alt.X(
                    "x:Q",
                    scale=alt.Scale(domain=[self.viz_xmin, self.viz_xmax], zero=False),
                    axis=None,
                ),
                y=alt.Y(
                    "y:Q",
                    scale=alt.Scale(domain=[self.viz_ymin, self.viz_ymax], zero=False),
                    axis=None,
                ),
                detail="edge_id:N",
                order="point_order:Q",
            )
            .properties(**chart_props)
        )


def _get_hex_vertices(
    center_x: float, center_y: float, size: float = 1.0
) -> list[tuple[float, float]]:
    """Get vertices for a hexagon centered at (center_x, center_y)."""
    vertices = [
        (center_x, center_y + size),  # top
        (center_x + size * np.sqrt(3) / 2, center_y + size / 2),  # top right
        (center_x + size * np.sqrt(3) / 2, center_y - size / 2),  # bottom right
        (center_x, center_y - size),  # bottom
        (center_x - size * np.sqrt(3) / 2, center_y - size / 2),  # bottom left
        (center_x - size * np.sqrt(3) / 2, center_y + size / 2),  # top left
    ]
    return vertices


def _edge_frame(edges):
    """Return one row per edge end point, keyed by edge id and point order."""
    edge_data = []
    for i, edge_tuple in enumerate(edges):
        p1, p2 = edge_tuple
        edge_data.append({"edge_id": i, "point_order": 0, "x": p1[0], "y": p1[1]})
        edge_data.append({"edge_id": i, "point_order": 1, "x": p2[0], "y": p2[1]})
    return pd.DataFrame(edge_data)
