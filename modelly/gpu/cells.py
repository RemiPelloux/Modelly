"""A ``CellIndex`` on the device: per-cell counts, neighbour sums and random moves.

``DeviceCellIndex(index, backend)`` copies the CSR adjacency of a
:class:`~modelly.space.cells.index.CellIndex` (the cells' ``connections``, in
their order) to the device once. Its three operations answer the same
questions as the host index, as array programs:

* ``counts(rows, weights)``: agents (or a quantity) per cell, a scatter-add;
* ``neighbor_sum(values)``: per cell, the sum over its neighbours, a gather and
  a segmented sum along the CSR rows;
* ``random_neighbor(rows, stream)``: a uniformly chosen neighbour per agent,
  with a bounded integer from a :class:`~modelly.gpu.streams.PhiloxStream`.

Integer counts and sums are exact, so they are identical on every backend.
Float sums are exact up to the order of additions: within a few ulps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from modelly.gpu.backend import Backend, get_backend

if TYPE_CHECKING:
    from modelly.gpu.streams import PhiloxDraw, PhiloxStream
    from modelly.space.cells.index import CellIndex


class DeviceCellIndex:
    """The adjacency of a cell space as device arrays.

    Args:
        index: the host ``CellIndex`` whose adjacency is copied.
        backend: a backend or backend name (see ``get_backend``).
    """

    def __init__(self, index: CellIndex, backend: Any = None) -> None:
        """Copy the CSR adjacency (row pointers and neighbour rows) to the device."""
        adjacency = index.adjacency
        self.backend: Backend = get_backend(backend)
        self.n = index.n
        self.dimensions = index.dimensions
        self._load(adjacency.indptr, adjacency.indices)

    @classmethod
    def from_csr(
        cls, indptr: np.ndarray, indices: np.ndarray, backend: Any = None
    ) -> DeviceCellIndex:
        """An index from CSR arrays directly (row pointers, then neighbour rows)."""
        self = cls.__new__(cls)
        self.backend = get_backend(backend)
        self.n = len(indptr) - 1
        self.dimensions = ()
        self._load(np.asarray(indptr), np.asarray(indices))
        return self

    def _load(self, indptr: np.ndarray, indices: np.ndarray) -> None:
        """Upload the CSR arrays and the row of every entry (for segmented sums)."""
        backend = self.backend
        dtype = backend.int_dtype
        self.indptr = backend.asarray(indptr.astype(np.int64), dtype=dtype)
        self.indices = backend.asarray(indices.astype(np.int64), dtype=dtype)
        degree = np.diff(indptr).astype(np.int64)
        entry_rows = np.repeat(np.arange(self.n, dtype=np.int64), degree)
        self._entry_rows = backend.asarray(entry_rows, dtype=dtype)
        self.degree = backend.asarray(degree, dtype=dtype)
        self.nnz = int(indices.shape[0])

    def __len__(self) -> int:
        """Return the number of cells."""
        return self.n

    def counts(self, rows: Any, weights: Any = None) -> Any:
        """Per-cell total of ``weights`` (or of ones) over the agents in ``rows``."""
        if weights is None:
            return self.backend.bincount(rows, self.n)
        return self.backend.segment_add(rows, weights, self.n)

    def neighbor_sum(self, values: Any) -> Any:
        """For every cell, the sum of ``values`` over its neighbouring cells."""
        xp = self.backend.xp
        gathered = xp.asarray(values)[self.indices]
        return self.backend.segment_add(self._entry_rows, gathered, self.n)

    def random_neighbor(self, rows: Any, stream: PhiloxStream | PhiloxDraw) -> Any:
        """One uniformly chosen neighbour row per entry of ``rows`` (from ``stream``).

        A row without neighbours is returned unchanged. ``stream`` is a
        ``PhiloxStream`` (its next draw is used) or one ``PhiloxDraw``.
        """
        xp = self.backend.xp
        rows = xp.asarray(rows)
        draw = stream.draws() if hasattr(stream, "draws") else stream
        if self.nnz == 0:
            return rows
        if self.backend.fused:
            counter = (0, draw.call, draw.stream.stream)
            csr = (self.indptr, self.indices)
            return self.backend.neighbor_at(rows, csr, counter, draw.stream.key)
        start = self.indptr[rows]
        degree = self.degree[rows]
        pick = start + draw.integers(degree, rows.shape[0])
        chosen = self.indices[xp.minimum(pick, self.nnz - 1)]
        return xp.where(degree > 0, chosen, rows)

    def to_layer(self, values: Any) -> Any:
        """Reshape a per-cell vector to the grid's dimensions."""
        if not self.dimensions:
            raise ValueError("to_layer needs a space with dimensions (a grid).")
        return self.backend.xp.asarray(values).reshape(self.dimensions)

    def __repr__(self) -> str:
        """Cells, connections and backend."""
        return f"<DeviceCellIndex {self.n} cells, {self.nnz} connections on {self.backend.name}>"
