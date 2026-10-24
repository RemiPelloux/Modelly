"""Combine the Altair structure, property layer and agent charts into one canvas."""

import altair as alt
import pandas as pd

# Size of the placeholder chart shown when there is nothing to draw.
EMPTY_CHART_WIDTH = 450
EMPTY_CHART_HEIGHT = 350
FRAME_STROKE_WIDTH = 1.5


def redraw_altair_canvas(renderer):
    """Redraw the Altair charts the renderer drew before and combine them."""
    structure = renderer.space_mesh if renderer.space_mesh else None
    agents = renderer.agent_mesh if renderer.agent_mesh else None
    prop_base, prop_cbar = renderer.property_layer_mesh or (None, None)

    if renderer.space_mesh:
        structure = renderer.draw_structure()
    if renderer.agent_mesh:
        agents = renderer.draw_agents()
    if renderer.property_layer_mesh:
        prop_base, prop_cbar = renderer.draw_property_layer()

    return compose_altair_canvas(structure, prop_base, agents, prop_cbar)


def compose_altair_canvas(structure, prop_base, agents, prop_cbar):
    """Layer the spatial charts, stack the colorbar below, and frame the result."""
    spatial_charts_list = [chart for chart in [structure, prop_base, agents] if chart]

    main_spatial = None
    if spatial_charts_list:
        main_spatial = (
            spatial_charts_list[0]
            if len(spatial_charts_list) == 1
            else alt.layer(*spatial_charts_list)
        )

    final_chart = _with_colorbar(main_spatial, prop_cbar)
    if final_chart is None:
        # If no charts are available, return an empty chart
        final_chart = (
            alt.Chart(pd.DataFrame())
            .mark_point()
            .properties(width=EMPTY_CHART_WIDTH, height=EMPTY_CHART_HEIGHT)
        )

    return final_chart.configure_view(stroke="black", strokeWidth=FRAME_STROKE_WIDTH)


def _with_colorbar(main_spatial, prop_cbar):
    """Combine the spatial chart with the colorbar chart; None when both are absent."""
    if main_spatial and prop_cbar:
        return alt.vconcat(main_spatial, prop_cbar).configure_view(stroke=None)
    if main_spatial:  # Only main_spatial, no prop_cbar
        return main_spatial
    if prop_cbar:  # Only prop_cbar, no main_spatial
        return prop_cbar
    return None
