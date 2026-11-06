"""Split a network into balanced parts with few edges between them.

``graph(parts)`` describes the split; ``.layout(network)`` applies it to a
``Network`` (or a networkx graph). The method is deterministic: nodes are
ordered by breadth-first search from a pseudo-peripheral node of each component (the banding order of Cuthill and McKee), the order is cut
into ``parts`` runs of nearly equal size, the larger first, and a few passes of
greedy boundary refinement (the k-way form of Fiduccia and Mattheyses) move a
border node to the neighbouring part it has most edges to, while every part
stays within ``imbalance`` of its target size. The same graph and node order
give the same parts in every process.

A ``GraphLayout`` answers the questions of a ``BlockLayout``: who owns a node
(``owner``, ``owners``) and which nodes of other parts lie within ``radius``
hops of a part (``halo``).
"""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from typing import Any

import numpy as np

DEFAULT_IMBALANCE = 0.03
DEFAULT_PASSES = 4


def _csr(graph: Any) -> tuple[list, np.ndarray, np.ndarray]:
    """The nodes of ``graph`` in its order and its adjacency as CSR arrays."""
    nodes = list(graph.nodes)
    position = {node: i for i, node in enumerate(nodes)}
    neighbours = [sorted(position[m] for m in graph.neighbors(n)) for n in nodes]
    indptr = np.cumsum([0, *(len(row) for row in neighbours)])
    flat = [m for row in neighbours for m in row]
    return nodes, indptr.astype(np.int64), np.asarray(flat, dtype=np.int64)


def neighbours_of(indptr: np.ndarray, indices: np.ndarray, nodes: np.ndarray):
    """The neighbours of every node in ``nodes``, concatenated (with repeats)."""
    starts = indptr[nodes]
    lengths = indptr[nodes + 1] - starts
    offsets = np.repeat(starts - (np.cumsum(lengths) - lengths), lengths)
    return indices[offsets + np.arange(lengths.sum())]


def _bfs(indptr: np.ndarray, indices: np.ndarray, start: int, seen: np.ndarray):
    """Nodes reached from ``start`` in breadth-first order; marks them in ``seen``."""
    order, queue = [], deque([start])
    seen[start] = True
    while queue:
        node = queue.popleft()
        order.append(node)
        for other in indices[indptr[node] : indptr[node + 1]].tolist():
            if not seen[other]:
                seen[other] = True
                queue.append(other)
    return order


def banded_order(indptr: np.ndarray, indices: np.ndarray) -> list[int]:
    """All nodes, component by component, each in BFS order from a far node."""
    n = len(indptr) - 1
    degree = np.diff(indptr)
    placed, probed = np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)
    order: list[int] = []
    for start in np.lexsort((np.arange(n), degree)).tolist():
        if placed[start]:
            continue
        probe = _bfs(indptr, indices, start, probed)
        probed[probe] = False
        order.extend(_bfs(indptr, indices, probe[-1], placed))
    return order


def _initial(order: list[int], parts: int) -> np.ndarray:
    """Part of each node: ``order`` cut into ``parts`` runs, larger runs first."""
    base, extra = divmod(len(order), parts)
    labels = np.repeat(np.arange(parts), [base + (p < extra) for p in range(parts)])
    assignment = np.empty(len(order), dtype=np.int64)
    assignment[np.asarray(order, dtype=np.int64)] = labels
    return assignment


def _best_move(counts: Counter[int], own: int) -> tuple[int, int]:
    """The part a node has most edges to (lowest index on ties) and the gain."""
    top = max(counts.values())
    best = min(part for part, count in counts.items() if count == top)
    return best, top - counts.get(own, 0)


def _refine(csr: tuple, assignment: np.ndarray, parts: int, imbalance: float):
    """Greedy boundary passes: move nodes to the part they connect to most.

    In Python lists: a pass visits every node in turn and looks at a few neighbours
    each, where numpy calls cost more than the work.
    """
    indptr, indices, passes = csr
    n = len(assignment)
    cap = int(np.ceil(n / parts * (1 + imbalance)))
    floor = max(1, int(np.floor(n / parts * (1 - imbalance))))
    sizes = np.bincount(assignment, minlength=parts).tolist()
    flat, bounds = indices.tolist(), indptr.tolist()
    rows = [flat[bounds[i] : bounds[i + 1]] for i in range(n)]
    part = assignment.tolist()
    for _ in range(passes):
        if not _refine_pass(rows, part, sizes, (cap, floor)):
            break
    assignment[:] = part
    return assignment


def _refine_pass(
    rows: list[list[int]], part: list[int], sizes: list[int], limits: tuple[int, int]
) -> int:
    """One pass in node order, updating ``part`` and ``sizes``; how many nodes moved."""
    cap, floor = limits
    moved = 0
    for node, row in enumerate(rows):
        own = part[node]
        counts = Counter(part[neighbour] for neighbour in row)
        if not row or (len(counts) == 1 and own in counts):
            continue
        best, gain = _best_move(counts, own)
        if gain > 0 and sizes[best] < cap and sizes[own] > floor:
            part[node], moved = best, moved + 1
            sizes[best] += 1
            sizes[own] -= 1
    return moved


@dataclass(frozen=True)
class GraphPartition:
    """A split of a network into ``parts`` parts (see the module docstring)."""

    parts: int
    imbalance: float = DEFAULT_IMBALANCE
    passes: int = DEFAULT_PASSES

    @property
    def partitions(self) -> int:
        """Number of parts."""
        return self.parts

    def layout(self, network: Any) -> GraphLayout:
        """The parts of ``network`` (a ``Network`` or a networkx graph)."""
        graph = getattr(network, "G", network)
        nodes, indptr, indices = _csr(graph)
        if not 1 <= self.parts <= len(nodes):
            raise ValueError(f"cannot split {len(nodes)} nodes into {self.parts} parts")
        assignment = _initial(banded_order(indptr, indices), self.parts)
        csr = (indptr, indices, self.passes)
        assignment = _refine(csr, assignment, self.parts, self.imbalance)
        return GraphLayout(nodes, assignment, indptr, indices)


def graph(parts: int, imbalance: float = DEFAULT_IMBALANCE) -> GraphPartition:
    """Split a network into ``parts`` balanced parts with few edges between them."""
    if parts < 1:
        raise ValueError(f"need at least one part, got {parts}")
    if imbalance < 0:
        raise ValueError(f"imbalance must be >= 0, got {imbalance}")
    return GraphPartition(parts, imbalance)


class GraphLayout:
    """The parts of one network: who owns each node, and each part's halo."""

    def __init__(self, nodes: list, assignment: np.ndarray, indptr, indices) -> None:
        """Parts given by ``assignment[i]`` for ``nodes[i]``, over CSR adjacency."""
        self.nodes = nodes
        self.assignment = assignment
        self._position = {node: i for i, node in enumerate(nodes)}
        self._indptr, self._indices = indptr, indices
        self._parts = int(assignment.max()) + 1 if len(assignment) else 0

    def __len__(self) -> int:
        """Number of parts."""
        return self._parts

    def owners(self, nodes: Iterable[Hashable]) -> np.ndarray:
        """The part owning each node."""
        position = self._position
        return self.assignment[np.fromiter((position[n] for n in nodes), np.int64)]

    def owner(self, node: Hashable) -> int:
        """The part owning ``node``."""
        return int(self.assignment[self._position[node]])

    def sizes(self) -> np.ndarray:
        """Nodes in each part."""
        return np.bincount(self.assignment, minlength=self._parts)

    def cut(self) -> int:
        """Edges whose ends lie in different parts."""
        rows = np.repeat(np.arange(len(self.nodes)), np.diff(self._indptr))
        crossing = self.assignment[rows] != self.assignment[self._indices]
        return int(crossing.sum()) // 2

    def halo(self, index: int, radius: int = 1) -> frozenset:
        """Nodes of other parts within ``radius`` hops of part ``index``."""
        if radius < 0:
            raise ValueError(f"radius must be non-negative, got {radius}")
        inside = self.assignment == index
        reach, frontier = inside.copy(), np.flatnonzero(inside)
        for _ in range(int(radius)):
            found = neighbours_of(self._indptr, self._indices, frontier)
            frontier = np.unique(found[~reach[found]])
            reach[frontier] = True
        return frozenset(self.nodes[i] for i in np.flatnonzero(reach & ~inside))

    def neighbours(self, index: int, radius: int = 1) -> frozenset[int]:
        """Parts owning a node of part ``index``'s halo."""
        halo = self.halo(index, radius)
        return frozenset(self.owners(halo).tolist()) if halo else frozenset()
