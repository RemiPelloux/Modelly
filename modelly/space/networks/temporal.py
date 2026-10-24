"""Temporal networks: edges that exist during an interval of model time.

Every edge has an activation time ``start`` and an end time ``end`` and is active on
``start <= time < end``. The network keeps two heaps of pending changes, so moving the
clock forward with ``advance_to`` touches only the edges that switch on or off in
between: O(changed edges x log edges). Neighbour queries read the active adjacency,
O(degree). Given a ``clock`` (anything with a ``time``, usually the model), every query
first advances to ``clock.time``, so the answers are always those of the current time.

Moving the clock backwards (a rewind) replays every edge from the start: O(edges).
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Hashable, Iterable, Iterator
from typing import TYPE_CHECKING, Any, NamedTuple

from modelly.space.networks.base import NodeRows, csr_from_rows

if TYPE_CHECKING:
    from scipy.sparse import csr_matrix

ALWAYS = (-math.inf, math.inf)
DEFAULT_WEIGHT = 1.0


class TemporalEdge(NamedTuple):
    """One edge with its lifetime, between node rows ``u`` and ``v``."""

    u: int
    v: int
    start: float
    end: float
    weight: float


class TemporalNetwork(NodeRows):
    """Edges with lifetimes, queried at the current time.

    Attributes:
        nodes: the node labels, in row order.
        time: the time the active edges correspond to.
        clock: an object with a ``time`` attribute that queries follow, or ``None``.
    """

    def __init__(
        self,
        nodes: int | Iterable[Hashable] = 0,
        directed: bool = False,
        clock: Any = None,
    ) -> None:
        """Create an empty temporal network.

        Args:
            nodes: a count (labels ``0 .. n-1``) or the node labels; more are added by edges.
            directed: whether edges are one-way.
            clock: an object with a ``time`` attribute (a ``Model``) queries advance to.
        """
        self._init_nodes(nodes)
        self.directed = directed
        self.clock = clock
        self.time = -math.inf
        self._edges: dict[int, TemporalEdge] = {}
        self._next_id = 0
        self._reset_activity()

    def _reset_activity(self) -> None:
        """No edge active and every edge's changes pending, as before any time."""
        self._active: set[int] = set()
        self._adjacency: dict[int, dict[int, dict[int, float]]] = {}
        self._starts: list[tuple[float, int]] = []
        self._ends: list[tuple[float, int]] = []
        self._matrix: csr_matrix | None = None
        for edge_id, edge in self._edges.items():
            self._schedule(edge_id, edge)

    def add_edge(
        self,
        u: Hashable,
        v: Hashable,
        interval: tuple[float, float] = ALWAYS,
        weight: float = DEFAULT_WEIGHT,
    ) -> int:
        """Add an edge active on ``start <= time < end``, and return its id.

        Args:
            u: one end (added as a node if new).
            v: the other end.
            interval: ``(start, end)``; the default is always active.
            weight: the edge weight.
        """
        start, end = (float(t) for t in interval)
        if end <= start:
            raise ValueError(f"An edge must end after it starts, got {interval}.")
        edge = TemporalEdge(
            self.add_node(u), self.add_node(v), start, end, float(weight)
        )
        edge_id = self._next_id
        self._next_id += 1
        self._edges[edge_id] = edge
        self._schedule(edge_id, edge)
        self._apply_pending(self.time)
        return edge_id

    def remove_edge(self, edge_id: int) -> None:
        """Remove an edge, active or not; pending changes for it are dropped lazily."""
        if edge_id in self._active:
            self._deactivate(edge_id)
        del self._edges[edge_id]

    def _schedule(self, edge_id: int, edge: TemporalEdge) -> None:
        heapq.heappush(self._starts, (edge.start, edge_id))
        if math.isfinite(edge.end):
            heapq.heappush(self._ends, (edge.end, edge_id))

    def advance_to(self, time: float) -> int:
        """Make the active edges those of ``time``; return how many edges changed."""
        if time < self.time:
            self._reset_activity()
        self.time = time
        return self._apply_pending(time)

    def _apply_pending(self, time: float) -> int:
        changed = 0
        while self._starts and self._starts[0][0] <= time:
            _, edge_id = heapq.heappop(self._starts)
            edge = self._edges.get(edge_id)
            if edge is not None and edge.end > time and edge_id not in self._active:
                self._activate(edge_id)
                changed += 1
        while self._ends and self._ends[0][0] <= time:
            _, edge_id = heapq.heappop(self._ends)
            if edge_id in self._active:
                self._deactivate(edge_id)
                changed += 1
        return changed

    def _pairs(self, edge: TemporalEdge) -> tuple[tuple[int, int], ...]:
        if self.directed or edge.u == edge.v:
            return ((edge.u, edge.v),)
        return ((edge.u, edge.v), (edge.v, edge.u))

    def _activate(self, edge_id: int) -> None:
        edge = self._edges[edge_id]
        self._active.add(edge_id)
        for i, j in self._pairs(edge):
            self._adjacency.setdefault(i, {}).setdefault(j, {})[edge_id] = edge.weight
        self._matrix = None

    def _deactivate(self, edge_id: int) -> None:
        edge = self._edges[edge_id]
        self._active.discard(edge_id)
        for i, j in self._pairs(edge):
            parallel = self._adjacency[i][j]
            del parallel[edge_id]
            if not parallel:
                del self._adjacency[i][j]
        self._matrix = None

    def _sync(self) -> None:
        """Advance to the clock's time, if a clock is set."""
        if self.clock is not None and self.clock.time != self.time:
            self.advance_to(self.clock.time)

    def neighbors(self, node: Hashable) -> list:
        """The nodes linked to ``node`` by an active edge."""
        self._sync()
        return [self.nodes[j] for j in self._adjacency.get(self.row(node), {})]

    def weighted_neighbors(self, node: Hashable) -> dict:
        """Neighbour label to the summed weight of the active edges to it."""
        self._sync()
        targets = self._adjacency.get(self.row(node), {})
        return {self.nodes[j]: sum(p.values()) for j, p in targets.items()}

    def degree(self, node: Hashable) -> int:
        """The number of distinct active neighbours of ``node``."""
        self._sync()
        return len(self._adjacency.get(self.row(node), {}))

    def has_edge(self, u: Hashable, v: Hashable) -> bool:
        """Whether an active edge links ``u`` to ``v``."""
        self._sync()
        return self.row(v) in self._adjacency.get(self.row(u), {})

    def active_edges(self) -> Iterator[tuple[Any, Any, float]]:
        """``(u, v, weight)`` for every active edge."""
        self._sync()
        for edge_id in sorted(self._active):
            edge = self._edges[edge_id]
            yield self.nodes[edge.u], self.nodes[edge.v], edge.weight

    def number_of_active_edges(self) -> int:
        """The number of active edges."""
        self._sync()
        return len(self._active)

    def adjacency(self) -> csr_matrix:
        """The active adjacency (summed weights) as a CSR matrix, rows in ``nodes`` order."""
        self._sync()
        if self._matrix is None or self._matrix.shape[0] != len(self.nodes):
            summed = {
                i: {j: sum(p.values()) for j, p in targets.items()}
                for i, targets in self._adjacency.items()
            }
            self._matrix = csr_from_rows(summed, len(self.nodes))
        return self._matrix
