"""Altair chart of a space's agents (and property layers) for the SpaceAltair component."""

import altair as alt

from modelly.space import DiscreteSpace, Grid
from modelly.space.continuous import ContinuousSpace
from modelly.viz.altair.property_layers import chart_property_layers

_CHART_SIZE = 300
# Default marker area, auto-scaled by the grid area: _MARKER_AREA / min(width, height) ** 2
_MARKER_AREA = 30000
_INVALID_TOOLTIPS = ["color", "size", "x", "y"]


def _portrayal_to_dict(portrayal_result, agent):
    """Convert AgentPortrayalStyle to dict or return dict as-is."""
    from modelly.viz.components import AgentPortrayalStyle  # noqa

    if isinstance(portrayal_result, AgentPortrayalStyle):
        # Convert AgentPortrayalStyle to dict for Altair
        # Altair only uses 'color' and 'size' from the portrayal
        agent_data = {"id": getattr(agent, "unique_id", id(agent))}
        if portrayal_result.color is not None:
            agent_data["color"] = portrayal_result.color
        if portrayal_result.size is not None:
            agent_data["size"] = portrayal_result.size
        return agent_data
    else:
        return portrayal_result


def _get_agent_data_new_discrete_space(space: DiscreteSpace, agent_portrayal):
    """Format agent portrayal data for new-style discrete spaces.

    Args:
        space: the modelly.space.Grid instance
        agent_portrayal: the agent portrayal callable

    Returns:
        list of dicts

    """
    all_agent_data = []

    for cell in space.all_cells:
        for agent in cell.agents:
            agent_data = _portrayal_to_dict(agent_portrayal(agent), agent)
            agent_data["x"] = cell.coordinate[0]
            agent_data["y"] = cell.coordinate[1]
            all_agent_data.append(agent_data)
    return all_agent_data


def _get_agent_data_continuous_space(space: ContinuousSpace, agent_portrayal):
    """Format agent portrayal data for continuous space.

    Args:
        space: the ContinuousSpace instance
        agent_portrayal: the agent portrayal callable

    Returns:
        list of dicts
    """
    all_agent_data = []
    for agent in space._agent_to_index:
        agent_data = _portrayal_to_dict(agent_portrayal(agent), agent)
        agent_data["x"] = agent.pos[0]
        agent_data["y"] = agent.pos[1]
        all_agent_data.append(agent_data)
    return all_agent_data


def _get_agent_data(space, agent_portrayal) -> list[dict]:
    """Collect the portrayal data of every agent in a grid or continuous space."""
    match space:
        case Grid():
            return _get_agent_data_new_discrete_space(space, agent_portrayal)
        case ContinuousSpace():
            return _get_agent_data_continuous_space(space, agent_portrayal)
        case _:
            raise NotImplementedError(
                f"visualizing {type(space)} is currently not supported through altair"
            )


def _tooltips(first_agent: dict) -> list:
    """Return a tooltip per portrayal key of the first agent, except the drawn ones."""
    return [
        alt.Tooltip(
            key,
            type="quantitative" if isinstance(value, (int, float)) else "nominal",
        )
        for key, value in first_agent.items()
        if key not in _INVALID_TOOLTIPS
    ]


def _agent_encoding(space, all_agent_data: list[dict]) -> dict:
    """Return the encoding channels of the agent chart."""
    first_agent = all_agent_data[0] if all_agent_data else {}
    x_y_type = "ordinal" if not isinstance(space, ContinuousSpace) else "nominal"

    encoding_dict = {
        "x": alt.X("x", axis=None, type=x_y_type),
        "y": alt.Y("y", axis=None, type=x_y_type),
        "tooltip": _tooltips(first_agent),
    }

    if "color" in first_agent:
        unique_colors = list({agent_data["color"] for agent_data in all_agent_data})
        encoding_dict["color"] = alt.Color(
            "color:N",
            scale=alt.Scale(domain=unique_colors, range=unique_colors),
        )

    if "size" in first_agent:
        encoding_dict["size"] = alt.Size("size", type="quantitative")
    return encoding_dict


def _agent_chart(space, all_agent_data: list[dict]) -> alt.Chart:
    """Draw the agents as filled points."""
    encoding_dict = _agent_encoding(space, all_agent_data)
    agent_chart = (
        alt.Chart(
            alt.Data(values=all_agent_data if all_agent_data else []),
            encoding=alt.Encoding(**encoding_dict),
        )
        .mark_point(filled=True)
        .properties(width=_CHART_SIZE, height=_CHART_SIZE)
    )

    # This is the default value for the marker size, which auto-scales according to the grid area.
    if "size" not in encoding_dict:
        length = min(space.width, space.height)
        agent_chart = agent_chart.mark_point(size=_MARKER_AREA / length**2, filled=True)
    return agent_chart


def _draw_grid(space, agent_portrayal, property_layer_portrayal):
    all_agent_data = _get_agent_data(space, agent_portrayal)
    agent_chart = _agent_chart(space, all_agent_data)
    cbar_chart = None

    if property_layer_portrayal is not None:
        chart_width = agent_chart.properties().width
        chart_height = agent_chart.properties().height
        base_chart, cbar_chart = chart_property_layers(
            space=space,
            property_layer_portrayal=property_layer_portrayal,
            chart_width=chart_width,
            chart_height=chart_height,
        )

        base_chart = alt.layer(base_chart, agent_chart)
    else:
        base_chart = agent_chart
    if cbar_chart is not None:
        base_chart = alt.vconcat(base_chart, cbar_chart).configure_view(stroke=None)
    return base_chart
