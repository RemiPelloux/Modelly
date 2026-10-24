"""Region neighbourhoods of a ``GeoSpace``: contiguity (queen, rook) and distance."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import shapely

if TYPE_CHECKING:
    import geopandas as gpd
    from scipy.sparse import csr_matrix

# Region row of a point that lies in no region.
NO_REGION = -1
CONTIGUITY_KINDS = ("queen", "rook")


class RegionQueriesMixin:
    """Neighbourhoods between the polygons of ``regions``, built on one STRtree.

    Relies on the host providing ``regions`` (a GeoDataFrame), and the cache slots
    ``_region_tree_cache`` and ``_contiguity_cache``.
    """

    regions: gpd.GeoDataFrame
    _region_tree_cache: shapely.STRtree | None
    _contiguity_cache: dict[str, Any]

    @property
    def _region_tree(self) -> shapely.STRtree:
        """The STRtree over the region polygons, built on first use."""
        if self._region_tree_cache is None:
            self._region_tree_cache = shapely.STRtree(self.regions.geometry.values)
        return self._region_tree_cache

    def contiguity(self, kind: str = "queen") -> csr_matrix:
        """The region adjacency as a symmetric CSR matrix, rows in ``regions`` order.

        Args:
            kind: ``"queen"``: regions sharing at least one point are neighbours;
                ``"rook"``: they must share a border of positive length.
        """
        if kind not in CONTIGUITY_KINDS:
            raise ValueError(f"kind must be one of {CONTIGUITY_KINDS}, not {kind!r}.")
        if kind not in self._contiguity_cache:
            self._contiguity_cache[kind] = self._build_contiguity(kind)
        return self._contiguity_cache[kind]

    def _build_contiguity(self, kind: str) -> csr_matrix:
        from scipy.sparse import csr_matrix  # noqa: PLC0415 - scipy is heavy

        geoms = self.regions.geometry.values
        n = len(geoms)
        left, right = self._region_tree.query(geoms, predicate="intersects")
        keep = left != right
        left, right = left[keep], right[keep]
        if kind == "rook" and left.size:
            shared = shapely.intersection(
                shapely.boundary(geoms[left]), shapely.boundary(geoms[right])
            )
            keep = shapely.length(shared) > 0
            left, right = left[keep], right[keep]
        data = np.ones(left.shape[0], dtype=np.int8)
        return csr_matrix((data, (left, right)), shape=(n, n))

    def region_neighbors(
        self, label: Any, kind: str = "queen", distance: float | None = None
    ) -> list:
        """Labels of the regions next to region ``label``.

        Args:
            label: the region label.
            kind: ``"queen"`` or ``"rook"`` contiguity, used when ``distance`` is ``None``.
            distance: if given, every other region within this distance of ``label``.
        """
        row = self.regions.index.get_loc(label)
        if distance is None:
            adjacency = self.contiguity(kind)
            rows = adjacency.indices[adjacency.indptr[row] : adjacency.indptr[row + 1]]
        else:
            polygon = self.regions.geometry.values[row]
            rows = self._region_tree.query(
                polygon, predicate="dwithin", distance=distance
            )
            rows = rows[rows != row]
        return list(self.regions.index[np.sort(rows)])

    def regions_within(self, geometry: Any, distance: float | None = None) -> list:
        """Labels of the regions that intersect ``geometry``, or lie within ``distance`` of it."""
        if distance is None:
            rows = self._region_tree.query(geometry, predicate="intersects")
        else:
            rows = self._region_tree.query(
                geometry, predicate="dwithin", distance=distance
            )
        return list(self.regions.index[np.sort(rows)])
