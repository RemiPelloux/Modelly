"""Drawer for continuous spaces."""

import altair as alt
import matplotlib.pyplot as plt
import pandas as pd

from modelly.space.continuous import ContinuousSpace
from modelly.viz.render.drawers.base import BaseSpaceDrawer, chart_properties

# Dash pattern (offset, (on, off)) of the border of a toroidal space.
TORUS_BORDER_DASH = (0, (5, 10))


class ContinuousSpaceDrawer(BaseSpaceDrawer):
    """Drawer for continuous spaces."""

    def __init__(self, space: ContinuousSpace, viz_dims: tuple[int, int] = (0, 1)):
        """Initialize the continuous space drawer.

        Args:
            space: The continuous space to draw.
            viz_dims: The pair of dimension indices to project onto the x and y axes.

        Raises:
            ValueError: If the space has fewer than two dimensions.
            ValueError: If viz_dims does not contain exactly two distinct valid indices.
        """
        super().__init__(space)
        # Default is the classic 2D XY plane.
        self.viz_dims: tuple[int, int] = (0, 1)
        self.set_viz_dims(viz_dims)

    def set_viz_dims(self, viz_dims: tuple[int, int]) -> None:
        """Set which dimensions are visualized on the x and y axes.

        Args:
            viz_dims: Tuple of two distinct dimension indices.

        Raises:
            ValueError: If viz_dims is invalid for the underlying space.
        """
        self._validate_viz_dims(viz_dims)
        # Normalize to a plain tuple[int, int]
        self.viz_dims = (int(viz_dims[0]), int(viz_dims[1]))
        self._update_viz_params()

    def _validate_viz_dims(self, viz_dims) -> None:
        """Validate viz_dims against the underlying space."""
        ndims = getattr(self.space, "ndims", self.space.dimensions.shape[0])
        if ndims < 2:
            raise ValueError(
                "Continuous space visualization requires at least 2 dimensions"
            )

        if not isinstance(viz_dims, (tuple, list)) or len(viz_dims) != 2:
            raise ValueError("viz_dims must contain exactly two distinct dimensions")

        i, j = viz_dims
        if not isinstance(i, int) or not isinstance(j, int) or i == j:
            raise ValueError("viz_dims must contain exactly two distinct dimensions")

        if any(dim < 0 or dim >= ndims for dim in (i, j)):
            raise ValueError(f"viz_dims must be within [0, {ndims - 1}] for this space")

    def _update_viz_params(self) -> None:
        """Recompute visualization limits and marker defaults."""
        i, j = self.viz_dims
        self._set_padded_limits(self.space.dimensions[i], self.space.dimensions[j])

    def project(self, position):
        """Project an n-dimensional position onto the configured 2D plane."""
        i, j = self.viz_dims
        return position[i], position[j]

    def draw_matplotlib(self, ax=None, **draw_space_kwargs):
        """Draw the continuous space using matplotlib.

        Args:
            ax: Matplotlib axes object to draw on.
            **draw_space_kwargs: Keyword arguments for styling the axis frame. You may
                optionally pass ``viz_dims=(i, j)`` to select which two dimensions of an
                n-dimensional space are projected to x/y.

        Examples:
                linewidth=3, color="green"

        Returns:
            The modified axes object.
        """
        viz_dims = draw_space_kwargs.pop("viz_dims", None)
        if viz_dims is not None:
            self.set_viz_dims(viz_dims)

        if ax is None:
            _, ax = plt.subplots()

        border_style = "solid" if not self.space.torus else TORUS_BORDER_DASH
        spine_kwargs = {"linewidth": 1.5, "color": "black", "linestyle": border_style}
        spine_kwargs.update(draw_space_kwargs)

        for spine in ax.spines.values():
            spine.set(**spine_kwargs)

        ax.set_xlim(self.viz_xmin, self.viz_xmax)
        ax.set_ylim(self.viz_ymin, self.viz_ymax)

        return ax

    def draw_altair(self, chart_width=450, chart_height=350, **draw_chart_kwargs):
        """Draw the continuous space using Altair.

        Args:
            chart_width: Width for the shown chart.
            chart_height: Height for the shown chart.
            **draw_chart_kwargs: Keyword arguments for styling the chart's view properties.
                You may optionally pass ``viz_dims=(i, j)`` to select which two dimensions of an
                n-dimensional space are projected to x/y.

        Returns:
            An Altair Chart object representing the space.
        """
        viz_dims = draw_chart_kwargs.pop("viz_dims", None)
        if viz_dims is not None:
            self.set_viz_dims(viz_dims)

        chart_props = chart_properties(chart_width, chart_height, draw_chart_kwargs)

        chart = (
            alt.Chart(pd.DataFrame([{}]))
            .mark_rect(color="transparent")
            .encode(
                x=alt.X(scale=alt.Scale(domain=[self.viz_xmin, self.viz_xmax])),
                y=alt.Y(scale=alt.Scale(domain=[self.viz_ymin, self.viz_ymax])),
            )
            .properties(**chart_props)
        )

        return chart
