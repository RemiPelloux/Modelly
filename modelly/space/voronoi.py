"""Cell spaces based on Voronoi tessellation around seed points.

Creates irregular spatial divisions by building cells around seed points,
where each cell contains the area closer to its seed than any other.
Features:
- Organic-looking spaces from point sets
- Automatic neighbor determination
- Area-based cell capacities
- Natural regional divisions

Useful for models requiring irregular but mathematically meaningful spatial
divisions, like territories, service areas, or natural regions.
"""

from collections.abc import Callable, Sequence
from itertools import combinations
from random import Random

import numpy as np

from modelly.space.base import DiscreteSpace
from modelly.space.cells.cell import Cell
from modelly.space.delaunay import Delaunay


def round_float(x: float) -> int:  # noqa
    return int(x * 500)


class VoronoiGrid(DiscreteSpace):
    """Voronoi meshed GridSpace."""

    triangulation: Delaunay
    voronoi_coordinates: list
    regions: list

    def __init__(
        self,
        centroids_coordinates: Sequence[Sequence[float]],
        capacity: int | Callable | None = None,
        random: Random | None = None,
        cell_klass: type[Cell] = Cell,
    ) -> None:
        """A Voronoi Tessellation Grid.

        Given a set of points, this class creates a grid where a cell is centered in each point,
        its neighbors are given by Voronoi Tessellation cells neighbors
        and the capacity by the polygon area.

        Args:
            centroids_coordinates: coordinates of centroids to build the tessellation space
            capacity (int | Callable): capacity of the cells in the discrete space, or a
                callable computing the (int) capacity of a cell from its (float) polygon area
            random (Random): random number generator
            cell_klass (type[Cell]): type of cell class

        """
        # Separate callable capacity from numeric capacity before passing to base class
        capacity_function, numeric_capacity = (
            (capacity, None) if callable(capacity) else (None, capacity)
        )
        super().__init__(
            capacity=numeric_capacity, random=random, cell_klass=cell_klass
        )
        self.centroids_coordinates = centroids_coordinates
        self.capacity_function = capacity_function
        self._validate_parameters()

        from scipy.spatial import (  # noqa: PLC0415 - scipy is heavy; import lazily
            KDTree,
        )

        # Build KD-tree for fast nearest-centroid lookup
        self._kdtree = KDTree(np.array(centroids_coordinates))

        self._cells = self._create_cells(capacity, cell_klass)

        self.regions = None
        self.triangulation = None
        self.voronoi_coordinates = None

        self._connect_cells()
        self._build_cell_polygons()

    def _create_cells(
        self, capacity: int | Callable | None, cell_klass: type[Cell]
    ) -> dict[int, Cell]:
        """Create one cell per centroid, keyed by its integer index."""
        # Create cells with Integer coordinates and physical positions
        # coordinate is now an integer index
        return {
            i: cell_klass(
                coordinate=i,  # Integer index
                capacity=capacity,
                random=self.random,
                position=self.centroids_coordinates[i],  # Physical centroid position
            )
            for i in range(len(self.centroids_coordinates))
        }

    def find_nearest_cell(self, position: np.ndarray) -> Cell:
        """Find the Voronoi cell nearest to the given position.

        Args:
            position: Physical position [x, y]

        Returns:
            Cell: The Voronoi cell whose centroid is nearest to position
        """
        position = np.asarray(position)

        # Find nearest centroid using KD-tree
        _distance, index = self._kdtree.query(position)

        return self._cells[index]

    def _connect_cells(self) -> None:
        """Connect cells to neighbors based on given centroids and using Delaunay Triangulation."""
        self.triangulation = Delaunay()
        for centroid in self.centroids_coordinates:
            self.triangulation.add_point(centroid)

        for point in self.triangulation.export_triangles():
            for i, j in combinations(point, 2):
                # Use integer indices as connection keys
                self._cells[i].connect(self._cells[j], j)
                self._cells[j].connect(self._cells[i], i)

    def _validate_parameters(self) -> None:
        if self.capacity is not None and not isinstance(self.capacity, float | int):
            raise ValueError("Capacity must be a number or None.")

        if not isinstance(self.centroids_coordinates, Sequence) or not isinstance(
            self.centroids_coordinates[0], Sequence
        ):
            raise ValueError("Centroids should be a list of lists")
        dimension_1 = len(self.centroids_coordinates[0])
        for coordinate in self.centroids_coordinates:
            if dimension_1 != len(coordinate):
                raise ValueError("Centroid coordinates should be a homogeneous array")

    def _get_voronoi_regions(self) -> tuple:
        if self.voronoi_coordinates is None or self.regions is None:
            (
                self.voronoi_coordinates,
                self.regions,
            ) = self.triangulation.export_voronoi_regions()
        return self.voronoi_coordinates, self.regions

    @staticmethod
    def _compute_polygon_area(polygon: list) -> float:
        polygon = np.array(polygon)
        x = polygon[:, 0]
        y = polygon[:, 1]
        return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))

    def _build_cell_polygons(self):
        coordinates, regions = self._get_voronoi_regions()
        for region in regions:
            polygon = [coordinates[i] for i in regions[region]]
            self._cells[region].properties["polygon"] = polygon
            polygon_area = self._compute_polygon_area(polygon)
            self._cells[region].properties["area"] = polygon_area
            if self.capacity is not None:
                # User provided a fixed capacity — use it directly.
                self._cells[region].capacity = self.capacity
            elif self.capacity_function is not None:
                # No fixed capacity but a function was provided — derive from area.
                self._cells[region].capacity = self.capacity_function(polygon_area)
            # else: both are None — cell capacity stays None (no limit).
