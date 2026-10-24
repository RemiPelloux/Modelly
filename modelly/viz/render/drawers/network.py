"""Drawer for network spaces."""

import altair as alt
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

from modelly.viz.render.drawers.base import (
    BaseSpaceDrawer,
    Network,
    chart_properties,
)


class NetworkSpaceDrawer(BaseSpaceDrawer):
    """Drawer for network-based spaces."""

    def __init__(
        self,
        space: Network,
        layout_alg=nx.spring_layout,
        layout_kwargs=None,
    ):
        """Initialize the network space drawer.

        Args:
            space: The network space to draw
            layout_alg: NetworkX layout algorithm to use
            layout_kwargs: Keyword arguments for the layout algorithm
        """
        super().__init__(space)
        self.layout_alg = layout_alg
        self.layout_kwargs = layout_kwargs if layout_kwargs is not None else {"seed": 0}

        # gather locations for nodes in network
        self.graph = self.space.G

        self.pos = {}

        for node_id, cell in self.space._cells.items():
            if getattr(cell, "_position", None) is not None:
                self.pos[node_id] = cell.position

        x, y = list(zip(*self.pos.values())) if self.pos else ([0], [0])
        self._set_padded_limits((min(x), max(x)), (min(y), max(y)))

    def draw_matplotlib(self, ax=None, **draw_space_kwargs):
        """Draw the network using matplotlib.

        Args:
            ax: Matplotlib axes object to draw on.
            **draw_space_kwargs: Dictionaries of keyword arguments for styling.
                Can also handle zorder for both nodes and edges if passed.
                * ``node_kwargs``: A dict passed to nx.draw_networkx_nodes.
                * ``edge_kwargs``: A dict passed to nx.draw_networkx_edges.

        Returns:
            The modified axes object.
        """
        if ax is None:
            _, ax = plt.subplots()

        ax.set_axis_off()
        ax.set_xlim(self.viz_xmin, self.viz_xmax)
        ax.set_ylim(self.viz_ymin, self.viz_ymax)

        node_kwargs = {"alpha": 0.5}
        edge_kwargs = {"alpha": 0.5, "style": "--"}

        node_kwargs.update(draw_space_kwargs.get("node_kwargs", {}))
        edge_kwargs.update(draw_space_kwargs.get("edge_kwargs", {}))

        node_zorder = node_kwargs.pop("zorder", 1)
        edge_zorder = edge_kwargs.pop("zorder", 0)

        nodes = nx.draw_networkx_nodes(self.graph, self.pos, ax=ax, **node_kwargs)
        edges = nx.draw_networkx_edges(self.graph, self.pos, ax=ax, **edge_kwargs)

        if nodes:
            nodes.set_zorder(node_zorder)
        _set_edge_zorder(edges, edge_zorder)

        return ax

    def draw_altair(self, chart_width=450, chart_height=350, **draw_chart_kwargs):
        """Draw the network using Altair.

        Args:
            chart_width: Width for the shown chart
            chart_height: Height for the shown chart
            **draw_chart_kwargs: Dictionaries for styling the chart.
                * ``node_kwargs``: A dict of properties for the node's mark_point.
                * ``edge_kwargs``: A dict of properties for the edge's mark_rule.
                * Other kwargs (e.g., title, width) are passed to chart.properties().

        Returns:
            Altair chart object representing the network.
        """
        nodes_df, edge_positions = self._node_and_edge_frames()

        node_mark_kwargs = {"filled": True, "opacity": 0.5, "size": 500}
        edge_mark_kwargs = {"opacity": 0.5, "strokeDash": [5, 3]}

        node_mark_kwargs.update(draw_chart_kwargs.pop("node_kwargs", {}))
        edge_mark_kwargs.update(draw_chart_kwargs.pop("edge_kwargs", {}))

        chart_props = chart_properties(chart_width, chart_height, draw_chart_kwargs)

        edge_plot = self._edge_chart(edge_positions, edge_mark_kwargs)
        node_plot = (
            alt.Chart(nodes_df)
            .mark_point(**node_mark_kwargs)
            .encode(x="x", y="y", tooltip=["node"])
        )

        chart = edge_plot + node_plot

        if chart_props:
            chart = chart.properties(**chart_props)

        return chart

    def _node_and_edge_frames(self):
        """Return the node positions and the edges joined to both end positions."""
        nodes_df = pd.DataFrame(self.pos).T.reset_index()
        nodes_df.columns = ["node", "x", "y"]

        edges_df = pd.DataFrame(self.graph.edges(), columns=["source", "target"])
        edge_positions = edges_df.merge(
            nodes_df, how="left", left_on="source", right_on="node"
        ).merge(
            nodes_df,
            how="left",
            left_on="target",
            right_on="node",
            suffixes=("_source", "_target"),
        )
        return nodes_df, edge_positions

    def _edge_chart(self, edge_positions, edge_mark_kwargs):
        """Return the Altair rule chart drawing every edge."""
        return (
            alt.Chart(edge_positions)
            .mark_rule(**edge_mark_kwargs)
            .encode(
                x=alt.X(
                    "x_source",
                    scale=alt.Scale(domain=[self.viz_xmin, self.viz_xmax]),
                    axis=None,
                ),
                y=alt.Y(
                    "y_source",
                    scale=alt.Scale(domain=[self.viz_ymin, self.viz_ymax]),
                    axis=None,
                ),
                x2="x_target",
                y2="y_target",
            )
        )


def _set_edge_zorder(edges, edge_zorder):
    """Set the zorder of the drawn edges, a collection or a list of them."""
    # In some matplotlib versions, edges can be a list of collections
    if isinstance(edges, list):
        for edge_collection in edges:
            edge_collection.set_zorder(edge_zorder)
    elif edges:
        edges.set_zorder(edge_zorder)
