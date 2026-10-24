"""Node rows shared by the temporal and multilayer networks.

Nodes are any hashable labels; each gets an integer row, in insertion order, so the
network's adjacency is a sparse matrix whose rows line up with a per-node numpy vector
(an agent column, a state array). Edges live in dictionaries keyed by rows, so adding or
removing one edge costs O(1) and a neighbour query costs O(degree).
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from scipy.sparse import csr_matrix


class NodeRows:
    """Labels to rows and back, for a network over ``nodes``."""

    def _init_nodes(self, nodes: int | Iterable[Hashable]) -> None:
        """``nodes`` is a count (labels ``0 .. n-1``) or an iterable of distinct labels."""
        self.nodes: list[Hashable] = (
            list(range(nodes)) if isinstance(nodes, int) else list(nodes)
        )
        self._row: dict[Hashable, int] = {node: i for i, node in enumerate(self.nodes)}
        if len(self._row) != len(self.nodes):
            raise ValueError("Node labels must be distinct.")

    def __len__(self) -> int:
        """Return the number of nodes."""
        return len(self.nodes)

    def __contains__(self, node: Hashable) -> bool:
        """Whether ``node`` is a node of the network."""
        return node in self._row

    def add_node(self, node: Hashable) -> int:
        """Add ``node`` if it is new, and return its row."""
        row = self._row.get(node)
        if row is None:
            row = len(self.nodes)
            self._row[node] = row
            self.nodes.append(node)
            self._on_new_node(row)
        return row

    def _on_new_node(self, row: int) -> None:
        """Hook for subclasses that keep per-row storage."""

    def row(self, node: Hashable) -> int:
        """The row of ``node``."""
        try:
            return self._row[node]
        except KeyError as e:
            raise KeyError(f"{node!r} is not a node of this network.") from e

    def rows(self, nodes: Iterable[Hashable]) -> np.ndarray:
        """The rows of ``nodes``."""
        return np.fromiter((self.row(node) for node in nodes), dtype=np.intp)


def csr_from_rows(
    rows: dict[int, dict[int, float]], n: int, scale: float = 1.0
) -> csr_matrix:
    """A CSR matrix with entry ``scale * rows[i][j]`` for every stored pair."""
    from scipy.sparse import csr_matrix  # noqa: PLC0415 - scipy is heavy

    degrees = np.zeros(n, dtype=np.intp)
    for i, targets in rows.items():
        degrees[i] = len(targets)
    indptr = np.concatenate(([0], np.cumsum(degrees)))
    indices = np.empty(indptr[-1], dtype=np.intp)
    data = np.empty(indptr[-1], dtype=float)
    for i, targets in rows.items():
        start = indptr[i]
        indices[start : start + len(targets)] = list(targets)
        data[start : start + len(targets)] = list(targets.values())
    matrix = csr_matrix((data * scale, indices, indptr), shape=(n, n))
    matrix.sort_indices()
    return matrix
