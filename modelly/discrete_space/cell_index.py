"""Integer rows for the cells of a discrete space, and sparse operators over them.

Every discrete space (grid, network, Voronoi mesh) is a set of cells joined by
``connections``. Numbering the cells gives each one a row, and the connections
become a sparse adjacency matrix. Whole-population questions then cost one
numpy call each instead of one Python loop per agent:

* ``counts(rows)``: how many agents, or how much of a quantity, sit in each cell;
* ``neighbor_sum(values)``: for every cell, the sum of ``values`` over its neighbours;
* ``random_neighbor(rows)``: one uniformly chosen neighbour for every row.

Agents that declare a ``Column`` for their cell row (``row = Column(np.intp)``,
kept current with ``self.row = cell.index`` when they move) can combine these
with ``ColumnTable.draw`` into a vectorised step phase. See
``docs/vectorised_phases.md`` for the equivalence arguments.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from scipy.sparse import csr_matrix

    from modelly.agent import Agent
    from modelly.discrete_space.cell import Cell
    from modelly.discrete_space.discrete_space import DiscreteSpace
    from modelly.model import Model


class CellIndex:
    """Rows for the cells of ``space`` and the sparse adjacency between them.

    Building the index writes ``cell.index`` on every cell, in the order of
    ``space.all_cells``. For grids that order is the C order of the coordinates,
    so a per-cell vector reshaped to the grid's dimensions is a property layer.
    """

    def __init__(self, space: DiscreteSpace) -> None:
        """Number the cells of ``space``; the adjacency is built on first use."""
        cells = space.all_cells.cells
        for row, cell in enumerate(cells):
            cell.index = row
        self.cells: list[Cell] = cells
        self.n = len(cells)
        self.dimensions = tuple(getattr(space, "dimensions", ()))
        self._adjacency: csr_matrix | None = None
        # agent class -> (model, column name) for agents placed by a row column
        self._tracked: dict[type, tuple[Model, str]] = {}
        space._cell_index = self

    def track(self, model: Model, agent_class: type, column: str = "row") -> None:
        """Declare that ``agent_class`` keeps its cell as a row ``column``.

        Such agents are in no cell's agent list; tracking them makes the space
        list them (``space.agents``) and lets the visualisation place them at
        ``index.cells[agent.<column>]``.
        """
        self._tracked[agent_class] = (model, column)

    def tracked_agents(self) -> Iterator[Agent]:
        """The live agents of every tracked class, in table order."""
        for agent_class, (model, _) in self._tracked.items():
            if agent_class in model.columns:
                yield from model.columns[agent_class].agents

    def cell_of(self, agent: Agent) -> Cell:
        """The cell a tracked agent occupies, from its row column."""
        try:
            _, column = self._tracked[type(agent)]
        except KeyError as e:
            raise ValueError(
                f"{type(agent).__name__} has no cell and is not tracked; call "
                "CellIndex.track(model, agent_class, column) for row-placed agents."
            ) from e
        return self.cells[getattr(agent, column)]

    def __len__(self) -> int:
        """Return the number of cells."""
        return self.n

    def rows(self, cells: Iterable[Cell]) -> np.ndarray:
        """Return the row of each cell in ``cells``."""
        return np.fromiter((cell.index for cell in cells), dtype=np.intp)

    def counts(self, rows: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
        """Per-cell total of ``weights`` (or of ones) over the agents sitting in ``rows``."""
        if weights is None:
            return np.bincount(rows, minlength=self.n)
        return np.bincount(rows, weights=weights, minlength=self.n)

    @property
    def adjacency(self) -> csr_matrix:
        """The cell adjacency as a CSR matrix with one entry per connection."""
        if self._adjacency is None:
            self._adjacency = self._build_adjacency()
        return self._adjacency

    def _build_adjacency(self) -> csr_matrix:
        from scipy.sparse import csr_matrix  # noqa: PLC0415 - scipy is heavy

        cells = self.cells
        degrees = np.fromiter((len(cell.connections) for cell in cells), dtype=np.intp)
        indices = np.fromiter(
            (other.index for cell in cells for other in cell.connections.values()),
            dtype=np.intp,
            count=int(degrees.sum()),
        )
        indptr = np.concatenate(([0], np.cumsum(degrees)))
        data = np.ones(indices.shape[0], dtype=np.int32)
        return csr_matrix((data, indices, indptr), shape=(self.n, self.n))

    def neighbor_sum(self, values: np.ndarray) -> np.ndarray:
        """For every cell, the sum of ``values`` over its neighbouring cells."""
        return self.adjacency @ np.asarray(values)

    def random_neighbor(self, rows: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        """One uniformly chosen neighbour row per entry of ``rows``.

        A row without neighbours is returned unchanged.
        """
        adjacency = self.adjacency
        if adjacency.nnz == 0:
            return np.array(rows, copy=True)
        start = adjacency.indptr[rows]
        degree = adjacency.indptr[rows + 1] - start
        pick = start + (rng.random(rows.shape[0]) * degree).astype(np.intp)
        chosen = adjacency.indices[np.minimum(pick, adjacency.nnz - 1)]
        return np.where(degree > 0, chosen, rows)

    def to_layer(self, values: np.ndarray) -> np.ndarray:
        """Reshape a per-cell vector to the grid's dimensions (a property layer view)."""
        if not self.dimensions:
            raise ValueError("to_layer needs a space with dimensions (a grid).")
        return np.asarray(values).reshape(self.dimensions)
