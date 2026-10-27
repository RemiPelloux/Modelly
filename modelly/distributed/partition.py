"""Split a grid into rectangular blocks, one per worker, with their halos.

``grid_blocks(rows, cols)`` describes the split; ``.layout(grid)`` applies it to a
grid's dimensions and torus setting. A layout says which block owns a cell
(``owner``, ``owners``, ``owner_map``) and which cells of other blocks lie
within a radius of a block (``halo``): the ghost cells a worker must receive
from its neighbours before a step that looks that far.

Each axis is cut into nearly equal runs, the larger runs first, so the same
grid and split always give the same blocks, whichever process asks.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import cached_property
from itertools import product
from typing import Any

import numpy as np

AXES = 2


def _cuts(length: int, parts: int) -> tuple[int, ...]:
    """Boundaries splitting ``range(length)`` into ``parts`` runs, larger runs first."""
    if not 1 <= parts <= length:
        raise ValueError(f"cannot cut an axis of {length} cells into {parts} blocks")
    base, extra = divmod(length, parts)
    sizes = [base + (i < extra) for i in range(parts)]
    return tuple(int(c) for c in np.cumsum([0, *sizes]))


@dataclass(frozen=True)
class Block:
    """One block: cells with ``lower <= coordinate < upper`` on every axis."""

    index: int
    lower: tuple[int, int]
    upper: tuple[int, int]

    @property
    def shape(self) -> tuple[int, int]:
        """Cells along each axis."""
        return (self.upper[0] - self.lower[0], self.upper[1] - self.lower[1])

    def __contains__(self, coordinate: object) -> bool:
        """Whether ``coordinate`` is a cell of this block."""
        x, y = coordinate  # type: ignore[misc]
        return self.lower[0] <= x < self.upper[0] and self.lower[1] <= y < self.upper[1]

    def cells(self) -> Iterator[tuple[int, int]]:
        """The block's coordinates, row by row."""
        return product(
            range(self.lower[0], self.upper[0]), range(self.lower[1], self.upper[1])
        )


@dataclass(frozen=True)
class GridBlocks:
    """A split of a 2-D grid into ``rows`` by ``cols`` blocks."""

    rows: int
    cols: int

    @property
    def partitions(self) -> int:
        """Number of blocks."""
        return self.rows * self.cols

    def layout(self, grid: Any = None, *, dimensions=None, torus=None) -> BlockLayout:
        """The blocks of ``grid`` (or of explicit ``dimensions`` and ``torus``)."""
        dims = tuple(grid.dimensions if dimensions is None else dimensions)
        wraps = bool(getattr(grid, "torus", False) if torus is None else torus)
        if len(dims) != AXES:
            raise ValueError(f"grid blocks split 2-D grids, got dimensions {dims}")
        return BlockLayout(
            dims, wraps, _cuts(dims[0], self.rows), _cuts(dims[1], self.cols)
        )


def grid_blocks(rows: int, cols: int) -> GridBlocks:
    """Split a 2-D grid into ``rows`` by ``cols`` rectangular blocks."""
    if rows < 1 or cols < 1:
        raise ValueError(f"need at least one block per axis, got {rows} by {cols}")
    return GridBlocks(rows, cols)


class BlockLayout:
    """The blocks of one grid: who owns each cell, and each block's halo."""

    def __init__(self, dimensions, torus: bool, x_cuts, y_cuts) -> None:
        """Blocks bounded by ``x_cuts`` and ``y_cuts``, numbered row-major."""
        self.dimensions: tuple[int, int] = dimensions
        self.torus = torus
        self._cuts = (np.asarray(x_cuts), np.asarray(y_cuts))
        rows, cols = len(x_cuts) - 1, len(y_cuts) - 1
        self.blocks: tuple[Block, ...] = tuple(
            Block(i * cols + j, (x_cuts[i], y_cuts[j]), (x_cuts[i + 1], y_cuts[j + 1]))
            for i in range(rows)
            for j in range(cols)
        )
        self._cols = cols

    def __len__(self) -> int:
        """Number of blocks."""
        return len(self.blocks)

    def __iter__(self) -> Iterator[Block]:
        """The blocks in index order."""
        return iter(self.blocks)

    def owners(self, coordinates: Iterable) -> np.ndarray:
        """The index of the block owning each coordinate (an (n, 2) array or pairs)."""
        coords = np.asarray(
            list(coordinates)
            if not isinstance(coordinates, np.ndarray)
            else coordinates
        )
        coords = coords.reshape(-1, AXES)
        if ((coords < 0) | (coords >= self.dimensions)).any():
            raise ValueError(f"coordinates outside a grid of {self.dimensions}")
        rows = np.searchsorted(self._cuts[0], coords[:, 0], side="right") - 1
        cols = np.searchsorted(self._cuts[1], coords[:, 1], side="right") - 1
        return rows * self._cols + cols

    def owner(self, coordinate: tuple[int, int]) -> int:
        """The index of the block owning ``coordinate``."""
        return int(self.owners([coordinate])[0])

    @cached_property
    def owner_map(self) -> np.ndarray:
        """Block index of every cell, shaped like the grid (read-only)."""
        x, y = np.indices(self.dimensions)
        owners = self.owners(np.stack([x.ravel(), y.ravel()], axis=1)).reshape(
            self.dimensions
        )
        owners.flags.writeable = False
        return owners

    def halo(self, index: int, radius: int = 1) -> frozenset[tuple[int, int]]:
        """Cells of other blocks within ``radius`` steps (Chebyshev) of block ``index``."""
        if radius < 0:
            raise ValueError(f"radius must be non-negative, got {radius}")
        inside = self.owner_map == index
        reach = inside.copy()
        for dx, dy in product(range(-radius, radius + 1), repeat=AXES):
            reach |= self._shifted(inside, dx, dy)
        xs, ys = np.nonzero(reach & ~inside)
        return frozenset(zip(xs.tolist(), ys.tolist(), strict=True))

    def neighbours(self, index: int, radius: int = 1) -> frozenset[int]:
        """Blocks owning a cell of block ``index``'s halo."""
        halo = self.halo(index, radius)
        return frozenset(self.owners(sorted(halo)).tolist()) if halo else frozenset()

    def _shifted(self, mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
        """``mask`` moved by (dx, dy): wrapped on a torus, cut at the edges otherwise."""
        if self.torus:
            return np.roll(mask, (dx, dy), axis=(0, 1))
        out = np.zeros_like(mask)
        width, height = self.dimensions
        src_x, dst_x = (
            slice(max(0, -dx), width - max(0, dx)),
            slice(max(0, dx), width - max(0, -dx)),
        )
        src_y, dst_y = (
            slice(max(0, -dy), height - max(0, dy)),
            slice(max(0, dy), height - max(0, -dy)),
        )
        out[dst_x, dst_y] = mask[src_x, src_y]
        return out
