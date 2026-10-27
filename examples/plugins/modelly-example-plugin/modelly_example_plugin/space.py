"""A ring of cells: each cell has two neighbours, the last one next to the first."""

from __future__ import annotations

import networkx as nx

from modelly.space import Network


class Ring(Network):
    """``n`` cells in a circle, as a Modelly network space.

    Args:
        n: the number of cells (at least 3).
        random: the generator the space draws random cells from (``model.random``).
    """

    def __init__(self, n: int, random=None) -> None:
        """Build the circle of ``n`` cells."""
        super().__init__(nx.cycle_graph(n), random=random)
