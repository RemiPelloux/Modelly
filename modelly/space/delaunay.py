"""A 2D Delaunay triangulation (Bowyer-Watson), the basis of the Voronoi grid."""

from collections.abc import Sequence

import numpy as np

# The four corners of the bounding frame take the first coordinate slots.
FRAME_CORNERS = 4
TRIANGLE_SIDES = 3


class Delaunay:
    """Class to compute a Delaunay triangulation in 2D.

    ref: http://github.com/jmespadero/pyDelaunay2D
    """

    def __init__(self, center: tuple = (0, 0), radius: int = 9999) -> None:
        """Init and create a new frame to contain the triangulation.

        Args:
            center: Optional position for the center of the frame. Default (0,0)
            radius: Optional distance from corners to the center.
        """
        center = np.asarray(center)
        # Create coordinates for the corners of the frame
        self.coords = [
            center + radius * np.array((-1, -1)),
            center + radius * np.array((+1, -1)),
            center + radius * np.array((+1, +1)),
            center + radius * np.array((-1, +1)),
        ]

        # Create two dicts to store triangle neighbours and circumcircles.
        self.triangles = {}
        self.circles = {}

        # Create two CCW triangles for the frame
        triangle1 = (0, 1, 3)
        triangle2 = (2, 3, 1)
        self.triangles[triangle1] = [triangle2, None, None]
        self.triangles[triangle2] = [triangle1, None, None]

        # Compute circumcenters and circumradius for each triangle
        for t in self.triangles:
            self.circles[t] = self._circumcenter(t)

    def _circumcenter(self, triangle: list) -> tuple:
        """Compute circumcenter and circumradius of a triangle in 2D."""
        points = np.asarray([self.coords[v] for v in triangle])
        points2 = np.dot(points, points.T)
        a = np.block(
            [[2 * points2, np.array([[1], [1], [1]])], [np.array([[1, 1, 1, 0]])]]
        )

        b = np.hstack((np.sum(points * points, axis=1), [1]))
        x = np.linalg.solve(a, b)
        bary_coords = x[:-1]
        center = np.dot(bary_coords, points)

        radius = np.sum(np.square(points[0] - center))  # squared distance
        return (center, radius)

    def _in_circle(self, triangle: list, point: list) -> bool:
        """Check if point p is inside of precomputed circumcircle of triangle."""
        center, radius = self.circles[triangle]
        return np.sum(np.square(center - point)) <= radius

    def add_point(self, point: Sequence) -> None:
        """Add a point to the current DT, and refine it using Bowyer-Watson."""
        point_index = len(self.coords)
        self.coords.append(np.asarray(point))

        bad_triangles = []
        for triangle in self.triangles:
            if self._in_circle(triangle, point):
                bad_triangles.append(triangle)

        boundary = self._cavity_boundary(bad_triangles)

        for triangle in bad_triangles:
            del self.triangles[triangle]
            del self.circles[triangle]

        self._fill_cavity(point_index, boundary)

    def _cavity_boundary(self, bad_triangles: list) -> list:
        """Walk the edge of the triangles ``bad_triangles`` covers, in CCW order."""
        boundary = []
        triangle = bad_triangles[0]
        edge = 0

        while True:
            opposite_triangle = self.triangles[triangle][edge]
            if opposite_triangle not in bad_triangles:
                boundary.append(
                    (
                        triangle[(edge + 1) % TRIANGLE_SIDES],
                        triangle[(edge - 1) % TRIANGLE_SIDES],
                        opposite_triangle,
                    )
                )
                edge = (edge + 1) % TRIANGLE_SIDES
                if boundary[0][0] == boundary[-1][1]:
                    break
            else:
                edge = (
                    self.triangles[opposite_triangle].index(triangle) + 1
                ) % TRIANGLE_SIDES
                triangle = opposite_triangle
        return boundary

    def _fill_cavity(self, point_index: int, boundary: list) -> None:
        """Join the new point to every boundary edge and link the new triangles."""
        new_triangles = []
        for e0, e1, opposite_triangle in boundary:
            triangle = (point_index, e0, e1)
            self.circles[triangle] = self._circumcenter(triangle)
            self.triangles[triangle] = [opposite_triangle, None, None]
            if opposite_triangle:
                for i, neighbor in enumerate(self.triangles[opposite_triangle]):
                    if neighbor and e1 in neighbor and e0 in neighbor:
                        self.triangles[opposite_triangle][i] = triangle

            new_triangles.append(triangle)

        n = len(new_triangles)
        for i, triangle in enumerate(new_triangles):
            self.triangles[triangle][1] = new_triangles[(i + 1) % n]  # next
            self.triangles[triangle][2] = new_triangles[(i - 1) % n]  # previous

    def export_triangles(self) -> list:
        """Export the current list of Delaunay triangles."""
        triangles_list = [
            (a - 4, b - 4, c - 4)
            for (a, b, c) in self.triangles
            if a > 3 and b > 3 and c > 3
        ]
        return triangles_list

    def export_voronoi_regions(self):
        """Export coordinates and regions of Voronoi diagram as indexed data."""
        vor_coors, use_vertex, index = self._voronoi_vertices()

        regions = {}
        for i in range(FRAME_CORNERS, len(self.coords)):
            vertex = use_vertex[i][0][0]
            region = []
            for _ in range(len(use_vertex[i])):
                triangle = next(
                    triangle for triangle in use_vertex[i] if triangle[0] == vertex
                )
                region.append(index[triangle])
                vertex = triangle[1]
            regions[i - FRAME_CORNERS] = region

        return vor_coors, regions

    def _voronoi_vertices(self) -> tuple[list, dict, dict]:
        """Return the Voronoi vertices, each point's triangles and the triangle index."""
        use_vertex = {i: [] for i in range(len(self.coords))}
        vor_coors = []
        index = {}
        for triangle_index, (a, b, c) in enumerate(sorted(self.triangles)):
            vor_coors.append(self.circles[(a, b, c)][0])
            use_vertex[a] += [(b, c, a)]
            use_vertex[b] += [(c, a, b)]
            use_vertex[c] += [(a, b, c)]

            index[(a, b, c)] = triangle_index
            index[(c, a, b)] = triangle_index
            index[(b, c, a)] = triangle_index
        return vor_coors, use_vertex, index
