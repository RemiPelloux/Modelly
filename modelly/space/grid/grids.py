"""Grid-based cell space implementations with different connection patterns.

Provides several grid types for organizing cells:
- OrthogonalMooreGrid: 8 neighbors in 2D, (3^n)-1 in nD
- OrthogonalVonNeumannGrid: 4 neighbors in 2D, 2n in nD
- HexGrid: 6 neighbors in hexagonal pattern (2D only)

Each grid type supports optional wrapping (torus) and cell capacity limits.
Choose based on how movement and connectivity should work in your model -
Moore for unrestricted movement, Von Neumann for orthogonal-only movement,
or Hex for more uniform distances.

The shared machinery (cell creation, property layers, empty-cell selection,
pickling) lives in :mod:`modelly.space.grid.base`; ``Grid`` is
re-exported here so ``from modelly.space.grid.grids import Grid`` keeps working.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import product
from random import Random
from typing import TypeVar

import numpy as np

from modelly.space.cells.cell import Cell
from modelly.space.grid.base import GRID_2D, Grid
from modelly.space.grid.cell_class import pickle_gridcell, unpickle_gridcell

__all__ = [
    "Grid",
    "HexGrid",
    "OrthogonalMooreGrid",
    "OrthogonalVonNeumannGrid",
    "pickle_gridcell",
    "unpickle_gridcell",
]

T = TypeVar("T", bound=Cell)

HEX_SIZE = 1.0
HEX_ROW_SPACING = 1.5  # rows of pointy-topped hexes are 3/4 of a hex apart


class OrthogonalMooreGrid(Grid[T]):
    """Grid where cells are connected to their 8 neighbors.

    Example for two dimensions::

        directions = [
            (-1, -1), (-1, 0), (-1, 1),
            ( 0, -1),          ( 0, 1),
            ( 1, -1), ( 1, 0), ( 1, 1),
        ]
    """

    def _connect_cells_2d(self) -> None:
        # fmt: off
        offsets = [
            (-1, -1), (-1, 0), (-1, 1),
            ( 0, -1),          ( 0, 1),
            ( 1, -1), ( 1, 0), ( 1, 1),
        ]
        # fmt: on

        for cell in self.all_cells:
            self._connect_single_cell_2d(cell, offsets)

    def _connect_cells_nd(self) -> None:
        offsets = list(product([-1, 0, 1], repeat=len(self.dimensions)))
        offsets.remove((0,) * len(self.dimensions))  # Remove the central cell

        for cell in self.all_cells:
            self._connect_single_cell_nd(cell, offsets)


class OrthogonalVonNeumannGrid(Grid[T]):
    """Grid where cells are connected to their 4 neighbors.

    Example for two dimensions::

        directions = [
                    (0, -1),
            (-1, 0),         ( 1, 0),
                    (0,  1),
        ]
    """

    def _connect_cells_2d(self) -> None:
        # fmt: off
        offsets = [
                    (-1, 0),
            (0, -1),         (0, 1),
                    ( 1, 0),
        ]
        # fmt: on

        for cell in self.all_cells:
            self._connect_single_cell_2d(cell, offsets)

    def _connect_cells_nd(self) -> None:
        offsets: list[tuple[int, ...]] = []
        dimensions = len(self.dimensions)
        for dim in range(dimensions):
            for delta in [
                -1,
                1,
            ]:  # Move one step in each direction for the current dimension
                offset = [0] * dimensions
                offset[dim] = delta
                offsets.append(tuple(offset))

        for cell in self.all_cells:
            self._connect_single_cell_nd(cell, offsets)


class HexGrid(Grid[T]):
    """A Grid with hexagonal tilling of the space.

    Functions according to even-r rules.
    See https://www.redblobgames.com/grids/hexagons/#neighbors-offset for more.

    Note:
        When torus=True, both width and height must be even.

    Raises:
        ValueError: If torus=True and either width or height is odd.
    """

    def __init__(
        self,
        dimensions: Sequence[int],
        torus: bool = False,
        capacity: float | None = None,
        random: Random | None = None,
        cell_klass: type[T] = Cell,
    ) -> None:
        """Initialize the hex grid.

        Args:
            dimensions: the dimensions of the space
            torus: whether the space wraps
            capacity: capacity of the grid cell
            random: a random number generator
            cell_klass: the base class to use for the cells
        """
        super().__init__(
            dimensions=dimensions,
            torus=torus,
            capacity=capacity,
            random=random,
            cell_klass=cell_klass,
        )
        self._init_hex_geometry()

    def _init_hex_geometry(self) -> None:
        """Calculate physical positions for all cells and build KD-Tree.

        Refer https://www.redblobgames.com/grids/hexagons/#hex-to-pixel for more detail
        """
        positions = []
        self._kdtree_coords = []

        for coord, cell in self._cells.items():
            col, row = coord
            x = HEX_SIZE * math.sqrt(3) * (col + 0.5 * (row % 2))
            y = HEX_SIZE * HEX_ROW_SPACING * row
            position = np.array([x, y])

            cell.position = position
            positions.append(position)
            self._kdtree_coords.append(coord)

        from scipy.spatial import (  # noqa: PLC0415 - scipy is heavy; import lazily
            KDTree,
        )

        self._kdtree = KDTree(np.array(positions))

    def find_nearest_cell(self, position: np.ndarray) -> T:
        """Find the hex cell at the given position."""
        position = np.asarray(position)

        if self.torus:
            width_pixels = self.dimensions[0] * math.sqrt(3)
            height_pixels = self.dimensions[1] * HEX_ROW_SPACING
            position = np.array(
                [position[0] % width_pixels, position[1] % height_pixels]
            )

        _, index = self._kdtree.query(position)
        coord = self._kdtree_coords[index]
        return self._cells[coord]

    def _connect_cells_2d(self) -> None:
        # fmt: off
        odd_offsets = [
                        (-1, -1), (0, -1),
                    ( -1, 0),        ( 1, 0),
                        ( -1, 1), (0, 1),
                ]
        even_offsets = [
                        (0, -1), (1, -1),
                    ( -1, 0),       ( 1, 0),
                        ( 0, 1), ( 1, 1),
                ]
        # fmt: on

        for cell in self.all_cells:
            i = cell.coordinate[1]
            offsets = even_offsets if i % 2 == 0 else odd_offsets
            self._connect_single_cell_2d(cell, offsets=offsets)

    def _connect_cells_nd(self) -> None:
        raise NotImplementedError("HexGrids are only defined for 2 dimensions")

    def _validate_parameters(self):
        super()._validate_parameters()
        if len(self.dimensions) != GRID_2D:
            raise ValueError("HexGrid must have exactly 2 dimensions.")
        if self.torus and (self.width % 2 != 0 or self.height % 2 != 0):
            raise ValueError(
                "HexGrid with torus=True requires both width and height to be even."
            )
