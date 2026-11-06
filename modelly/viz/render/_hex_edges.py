"""The unique edges of a hexagon mesh, shared by both hex grid drawers."""

from collections.abc import Sequence

import numpy as np

# Decimals kept when de-duplicating shared hexagon edges.
EDGE_ROUNDING_DECIMALS = 6

Point = tuple[float, float]
Edge = tuple[Point, Point]


def unique_edges(hexagons: Sequence[Sequence[Point]]) -> set[Edge]:
    """Each edge of the mesh once, its two end points sorted.

    The vertices are rounded in one array operation (the same ``np.round`` as one
    vertex at a time); the edges come out in the iteration order of the set that
    de-duplicates them, as before. Callers keep the set and must not change it.
    """
    edges: set[Edge] = set()
    if len(hexagons) == 0:
        return edges
    rounded = np.round(np.asarray(hexagons, dtype=float), EDGE_ROUNDING_DECIMALS)
    for vertices in rounded.tolist():
        points = [tuple(point) for point in vertices]
        for v1, v2 in zip(points, [*points[1:], points[0]]):
            edges.add((v1, v2) if v1 <= v2 else (v2, v1))
    return edges


def edge_array(edges: set[Edge]) -> np.ndarray:
    """``edges`` in their iteration order as a read-only (n, 2, 2) array of segments."""
    array = np.array(list(edges), dtype=float).reshape(-1, 2, 2)
    array.flags.writeable = False
    return array
