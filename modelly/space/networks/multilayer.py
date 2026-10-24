"""Multilayer networks: one set of nodes, several layers of weighted edges.

A contact network for an epidemic is the classic case: the same people are linked in a
household layer, a school layer and a work layer, each with its own edges and its own
weight (how much a contact on that layer counts). Queries take one layer, several, or
all of them combined, with ``combined weight = sum(layer weight * edge weight)``.

Edges are kept per layer in dictionaries of rows, so ``add_edge`` and ``remove_edge``
cost O(1) and ``neighbors`` costs O(degree). ``adjacency`` returns the sparse matrix for
vectorised steps (``adjacency() @ infected``); it is cached per layer and rebuilt, in
O(edges of that layer), on the first call after the layer changed.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from modelly.space.networks.base import NodeRows, csr_from_rows

if TYPE_CHECKING:
    from scipy.sparse import csr_matrix

DEFAULT_WEIGHT = 1.0
LayerSelection = str | Sequence[str] | None


class MultilayerNetwork(NodeRows):
    """Nodes linked on named layers, each layer with a weight.

    Attributes:
        nodes: the node labels, in row order.
        layer_weights: layer name to its weight in combined queries.
        directed: whether an edge ``u -> v`` leaves ``v -> u`` absent.
    """

    def __init__(
        self,
        nodes: int | Iterable[Hashable],
        layers: Mapping[str, float] | Iterable[str] = (),
        directed: bool = False,
    ) -> None:
        """Create a network over ``nodes``.

        Args:
            nodes: a count (labels ``0 .. n-1``) or the node labels.
            layers: layer names, or a mapping of layer name to weight (default 1).
            directed: whether edges are one-way.
        """
        self._init_nodes(nodes)
        self.directed = directed
        self.layer_weights: dict[str, float] = {}
        self._edges: dict[str, dict[int, dict[int, float]]] = {}
        self._matrices: dict[str, csr_matrix] = {}
        weights = (
            layers
            if isinstance(layers, Mapping)
            else dict.fromkeys(layers, DEFAULT_WEIGHT)
        )
        for name, weight in weights.items():
            self.add_layer(name, weight)

    @property
    def layers(self) -> list[str]:
        """The layer names, in the order they were added."""
        return list(self.layer_weights)

    def add_layer(self, name: str, weight: float = DEFAULT_WEIGHT) -> None:
        """Add an empty layer, or change the weight of an existing one."""
        self._edges.setdefault(name, {})
        self.layer_weights[name] = float(weight)

    def add_edge(
        self, u: Hashable, v: Hashable, layer: str, weight: float = DEFAULT_WEIGHT
    ) -> None:
        """Link ``u`` and ``v`` on ``layer`` (created if new); new nodes are added."""
        if layer not in self._edges:
            self.add_layer(layer)
        i, j = self.add_node(u), self.add_node(v)
        edges = self._edges[layer]
        edges.setdefault(i, {})[j] = float(weight)
        if not self.directed:
            edges.setdefault(j, {})[i] = float(weight)
        self._matrices.pop(layer, None)

    def add_edges(
        self,
        pairs: Iterable[tuple[Hashable, Hashable]],
        layer: str,
        weight: float = DEFAULT_WEIGHT,
    ) -> None:
        """Link every ``(u, v)`` of ``pairs`` on ``layer`` with the same ``weight``."""
        for u, v in pairs:
            self.add_edge(u, v, layer, weight)

    def remove_edge(self, u: Hashable, v: Hashable, layer: str) -> None:
        """Remove the edge between ``u`` and ``v`` on ``layer``."""
        i, j = self.row(u), self.row(v)
        edges = self._edges[layer]
        try:
            del edges[i][j]
            if not self.directed:
                del edges[j][i]
        except KeyError as e:
            raise KeyError(f"No edge {u!r}-{v!r} on layer {layer!r}.") from e
        self._matrices.pop(layer, None)

    def has_edge(self, u: Hashable, v: Hashable, layer: str | None = None) -> bool:
        """Whether ``u`` and ``v`` are linked on ``layer``, or on any layer."""
        i, j = self.row(u), self.row(v)
        return any(j in self._edges[name].get(i, ()) for name in self._select(layer))

    def neighbors(self, node: Hashable, layer: LayerSelection = None) -> list:
        """The nodes linked to ``node`` on the selected layers (all by default)."""
        return [self.nodes[j] for j in self._neighbor_weights(node, layer)]

    def weighted_neighbors(self, node: Hashable, layer: LayerSelection = None) -> dict:
        """Neighbour label to combined weight, ``sum(layer weight * edge weight)``."""
        weights = self._neighbor_weights(node, layer)
        return {self.nodes[j]: w for j, w in weights.items()}

    def _neighbor_weights(
        self, node: Hashable, layer: LayerSelection
    ) -> dict[int, float]:
        i = self.row(node)
        combined: dict[int, float] = {}
        for name in self._select(layer):
            scale = self.layer_weights[name]
            for j, w in self._edges[name].get(i, {}).items():
                combined[j] = combined.get(j, 0.0) + scale * w
        return combined

    def degree(self, node: Hashable, layer: LayerSelection = None) -> int:
        """The number of distinct neighbours of ``node`` on the selected layers."""
        return len(self._neighbor_weights(node, layer))

    def edges(self, layer: str) -> Iterator[tuple[Any, Any, float]]:
        """``(u, v, weight)`` for every edge of ``layer`` (each undirected edge once)."""
        for i, targets in self._edges[layer].items():
            for j, w in targets.items():
                if self.directed or i <= j:
                    yield self.nodes[i], self.nodes[j], w

    def number_of_edges(self, layer: LayerSelection = None) -> int:
        """The number of edges on the selected layers, counted per layer."""
        return sum(sum(1 for _ in self.edges(name)) for name in self._select(layer))

    def adjacency(self, layer: LayerSelection = None) -> csr_matrix:
        """The combined weighted adjacency of the selected layers, rows in ``nodes`` order."""
        names = self._select(layer)
        n = len(self.nodes)
        total = None
        for name in names:
            matrix = self._matrices.get(name)
            if matrix is None or matrix.shape[0] != n:
                matrix = csr_from_rows(self._edges[name], n)
                self._matrices[name] = matrix
            part = matrix * self.layer_weights[name]
            total = part if total is None else total + part
        if total is None:
            return csr_from_rows({}, n)
        return total.tocsr()

    def to_networkx(self, layer: LayerSelection = None) -> Any:
        """A NetworkX graph of the selected layers, with the combined ``weight`` on edges."""
        import networkx as nx  # noqa: PLC0415

        graph = nx.DiGraph() if self.directed else nx.Graph()
        graph.add_nodes_from(self.nodes)
        matrix = self.adjacency(layer).tocoo()
        graph.add_weighted_edges_from(
            (self.nodes[i], self.nodes[j], float(w))
            for i, j, w in zip(matrix.row, matrix.col, matrix.data)
        )
        return graph

    def _select(self, layer: LayerSelection) -> list[str]:
        """The layer names a selection stands for, checked."""
        if layer is None:
            return self.layers
        names = [layer] if isinstance(layer, str) else list(layer)
        unknown = [name for name in names if name not in self._edges]
        if unknown:
            raise KeyError(f"Unknown layer(s) {unknown}; layers are {self.layers}.")
        return names
