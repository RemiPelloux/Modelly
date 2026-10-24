"""Drawer for Voronoi diagram spaces, with Cohen-Sutherland line clipping."""

from itertools import pairwise

import altair as alt
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection

from modelly.space import VoronoiGrid
from modelly.viz.render.drawers.base import (
    BaseSpaceDrawer,
    chart_properties,
    line_mark_kwargs,
)

# Cohen-Sutherland region codes
_INSIDE, _LEFT, _RIGHT, _BOTTOM, _TOP = 0, 1, 2, 4, 8


class VoronoiSpaceDrawer(BaseSpaceDrawer):
    """Drawer for Voronoi diagram spaces."""

    def __init__(self, space: VoronoiGrid):
        """Initialize the Voronoi space drawer.

        Args:
            space: The Voronoi grid space to draw
        """
        super().__init__(space)
        # Use the Cell.position property for calculations
        positions = np.array([cell.position for cell in self.space.all_cells])
        if len(positions) > 0:
            x_min, y_min = positions.min(axis=0)
            x_max, y_max = positions.max(axis=0)
        else:
            x_max, x_min, y_max, y_min = 1, 0, 1, 0

        self._set_padded_limits((x_min, x_max), (y_min, y_max))

    def _clip_line(self, p1, p2, box):
        """Clips a line segment using the Cohen-Sutherland algorithm.

        Returns the clipped line segment (p1, p2) or None if it's outside.
        """
        return clip_line(p1, p2, box)

    def _get_clipped_segments(self):
        """Helper method to perform the segment extraction, de-duplication and clipping logic."""
        clip_box = (
            self.viz_xmin,
            self.viz_ymin,
            self.viz_xmax,
            self.viz_ymax,
        )

        unique_segments = set()
        for cell in self.space.all_cells.cells:
            vertices = [tuple(v) for v in cell.properties["polygon"]]
            for p1, p2 in pairwise([*vertices, vertices[0]]):
                # Sort to avoid duplicate segments going in opposite directions
                unique_segments.add(tuple(sorted((p1, p2))))

        # Clip each unique segment
        final_segments = []
        for p1, p2 in unique_segments:
            clipped_segment = self._clip_line(p1, p2, clip_box)
            if clipped_segment:
                final_segments.append(clipped_segment)

        return final_segments, clip_box

    def draw_matplotlib(self, ax=None, **draw_space_kwargs):
        """Draw the Voronoi diagram using matplotlib.

        Args:
            ax: Matplotlib axes object to draw on
            **draw_space_kwargs: Keyword arguments passed to matplotlib's LineCollection.

        Examples:
                lw=2, alpha=0.5, colors='red'

        Returns:
            The modified axes object
        """
        if ax is None:
            _, ax = plt.subplots()

        final_segments, clip_box = self._get_clipped_segments()

        ax.set_xlim(clip_box[0], clip_box[2])
        ax.set_ylim(clip_box[1], clip_box[3])

        if final_segments:
            # Define default styles for the plot
            style_args = {"colors": "k", "linestyle": "dotted", "lw": 1}
            style_args.update(draw_space_kwargs)

            # Create the LineCollection with the final styles
            lc = LineCollection(final_segments, **style_args)
            ax.add_collection(lc)

        return ax

    def draw_altair(self, chart_width=450, chart_height=350, **draw_chart_kwargs):
        """Draw the Voronoi diagram using Altair.

        Args:
            chart_width: Width for the shown chart
            chart_height: Height for the shown chart
            **draw_chart_kwargs: Additional keyword arguments for styling the chart.

        Examples:
                * Line properties like color, strokeDash, strokeWidth, opacity.
                * Other kwargs (e.g., width, title) apply to the chart.

        Returns:
            An Altair Chart object representing the Voronoi diagram.
        """
        final_segments, clip_box = self._get_clipped_segments()
        df = _segment_frame(final_segments)
        mark_kwargs = line_mark_kwargs(draw_chart_kwargs)
        chart_props = chart_properties(chart_width, chart_height, draw_chart_kwargs)

        chart = (
            alt.Chart(df)
            .mark_line(**mark_kwargs)
            .encode(
                x=alt.X(
                    "x:Q", scale=alt.Scale(domain=[clip_box[0], clip_box[2]]), axis=None
                ),
                y=alt.Y(
                    "y:Q", scale=alt.Scale(domain=[clip_box[1], clip_box[3]]), axis=None
                ),
                detail="line_id:N",
            )
            .properties(**chart_props)
        )
        return chart


def _segment_frame(segments):
    """Return one row per segment end point, keyed by line id."""
    final_data = []
    for i, (p1, p2) in enumerate(segments):
        final_data.append({"x": p1[0], "y": p1[1], "line_id": i})
        final_data.append({"x": p2[0], "y": p2[1], "line_id": i})
    return pd.DataFrame(final_data)


def _outcode(x, y, box):
    """Return the Cohen-Sutherland region code of a point."""
    min_x, min_y, max_x, max_y = box
    code = _INSIDE
    if x < min_x:
        code |= _LEFT
    elif x > max_x:
        code |= _RIGHT
    if y < min_y:
        code |= _BOTTOM
    elif y > max_y:
        code |= _TOP
    return code


def _boundary_point(start, end, outcode_out, box):
    """Return where the segment crosses the box edge named by the outside code."""
    (x1, y1), (x2, y2) = start, end
    min_x, min_y, max_x, max_y = box
    x, y = 0.0, 0.0

    # Check for horizontal line
    if y1 != y2:
        if outcode_out & _TOP:
            x = x1 + (x2 - x1) * (max_y - y1) / (y2 - y1)
            y = max_y
        elif outcode_out & _BOTTOM:
            x = x1 + (x2 - x1) * (min_y - y1) / (y2 - y1)
            y = min_y

    # Check for vertical line
    if x1 != x2:
        if outcode_out & _RIGHT:
            y = y1 + (y2 - y1) * (max_x - x1) / (x2 - x1)
            x = max_x
        elif outcode_out & _LEFT:
            y = y1 + (y2 - y1) * (min_x - x1) / (x2 - x1)
            x = min_x
    return x, y


def clip_line(p1, p2, box):
    """Clip a line segment to a (min_x, min_y, max_x, max_y) box (Cohen-Sutherland).

    Returns the clipped line segment (p1, p2) or None if it's outside.
    """
    x1, y1 = p1
    x2, y2 = p2
    outcode1 = _outcode(x1, y1, box)
    outcode2 = _outcode(x2, y2, box)

    while True:
        if not (outcode1 | outcode2):  # Both points inside
            return (x1, y1), (x2, y2)
        if outcode1 & outcode2:  # Both points share an outside region
            return None
        outcode_out = outcode1 if outcode1 else outcode2
        x, y = _boundary_point((x1, y1), (x2, y2), outcode_out, box)
        if outcode_out == outcode1:
            x1, y1 = x, y
            outcode1 = _outcode(x1, y1, box)
        else:
            x2, y2 = x, y
            outcode2 = _outcode(x2, y2, box)
