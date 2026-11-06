"""Split a continuous space into boxes holding nearly equal numbers of agents.

``kd(parts)`` describes the split; ``.layout(space)`` applies it to a
``ContinuousSpace`` from the positions of its agents. The domain is cut in two
along its longest side (the lowest axis on ties) at the position that leaves
``ceil(parts / 2) / parts`` of the points on the low side, halfway between the
two points either side of the cut; each side is cut again until there are
``parts`` boxes (recursive coordinate bisection, a k-d tree). The boxes cover
the whole domain, so a point that moves anywhere has an owner.

A ``KDLayout`` says which box owns a point (``owner``, ``owners``) and which
points lie within a distance of a box (``near``, wrapping on a torus): the
ghosts a worker sends before a phase that looks that far.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

HALF = 2
SLACK = 1e-9  # relative margin of ``reaches``: never skip a box over a rounding error


@dataclass(frozen=True)
class Box:
    """One box: points with ``lower <= x < upper`` on every axis."""

    index: int
    lower: tuple[float, ...]
    upper: tuple[float, ...]


def _cut(values: np.ndarray, share: int, parts: int, bounds: tuple[float, float]):
    """Where to cut ``values`` so that ``share`` of ``parts`` of them fall below."""
    if len(values) < HALF:
        return (bounds[0] + bounds[1]) / HALF
    ordered = np.sort(values)
    k = min(max(1, round(len(values) * share / parts)), len(values) - 1)
    return float((ordered[k - 1] + ordered[k]) / HALF)


def _split(points: np.ndarray, lower: np.ndarray, upper: np.ndarray, parts: int):
    """The boxes of ``parts`` parts of the box ``lower``..``upper``, low side first."""
    if parts == 1:
        return [(tuple(lower.tolist()), tuple(upper.tolist()))]
    axis = int(np.argmax(upper - lower))
    share = -(-parts // HALF)
    cut = _cut(points[:, axis], share, parts, (lower[axis], upper[axis]))
    low_upper, high_lower = upper.copy(), lower.copy()
    low_upper[axis] = high_lower[axis] = cut
    below = points[:, axis] < cut
    return _split(points[below], lower, low_upper, share) + _split(
        points[~below], high_lower, upper, parts - share
    )


@dataclass(frozen=True)
class KDPartition:
    """A split of a continuous space into ``parts`` boxes (see the module docstring)."""

    parts: int

    @property
    def partitions(self) -> int:
        """Number of boxes."""
        return self.parts

    def layout(self, space: Any = None, *, points=None, bounds=None) -> KDLayout:
        """The boxes of ``space`` (or of explicit ``points`` and ``bounds``)."""
        if space is not None:
            points, bounds = space.agent_positions, space.dimensions
        bounds = np.asarray(bounds, dtype=float)
        points = np.asarray(points, dtype=float).reshape(-1, len(bounds))
        boxes = _split(points, bounds[:, 0], bounds[:, 1], self.parts)
        torus = bool(getattr(space, "torus", False))
        return KDLayout([Box(i, lo, hi) for i, (lo, hi) in enumerate(boxes)], torus)


def kd(parts: int) -> KDPartition:
    """Split a continuous space into ``parts`` boxes of nearly equal population."""
    if parts < 1:
        raise ValueError(f"need at least one box, got {parts}")
    return KDPartition(parts)


class KDLayout:
    """The boxes of one continuous space: who owns a point, and who is near a box."""

    def __init__(self, boxes: list[Box], torus: bool = False) -> None:
        """Boxes covering the domain, numbered in bisection order."""
        self.boxes = tuple(boxes)
        self.torus = torus
        self._lower = np.array([b.lower for b in boxes], dtype=float)
        self._upper = np.array([b.upper for b in boxes], dtype=float)
        self._domain = (self._lower.min(axis=0), self._upper.max(axis=0))

    def __len__(self) -> int:
        """Number of boxes."""
        return len(self.boxes)

    def owners(self, points: Any) -> np.ndarray:
        """The box owning each point (an (n, d) array); the domain's top edge included."""
        points = np.asarray(points, dtype=float).reshape(-1, self._lower.shape[1])
        owners = np.zeros(len(points), dtype=np.intp)
        left = np.arange(len(points))  # the first box holding a point owns it
        top = self._upper == self._domain[1]
        for box, (lower, upper) in enumerate(
            zip(self._lower, self._upper, strict=True)
        ):
            if not left.size:
                break
            p = points[left]
            below = (p < upper) | (top[box] & (p <= upper))
            inside = ((p >= lower) & below).all(axis=1)
            owners[left[inside]] = box
            left = left[~inside]
        if left.size:
            raise ValueError("a point lies outside the partitioned domain")
        return owners

    def owner(self, point: Any) -> int:
        """The box owning ``point``."""
        return int(self.owners([point])[0])

    def distances(self, index: int, points: Any) -> np.ndarray:
        """Euclidean distance from each point to box ``index`` (wrapping on a torus)."""
        points = np.asarray(points, dtype=float).reshape(-1, self._lower.shape[1])
        lower, upper = self._lower[index], self._upper[index]
        gap = np.maximum(np.maximum(lower - points, points - upper), 0.0)
        if self.torus:
            size = self._domain[1] - self._domain[0]
            for shift in (size, -size):
                moved = points + shift
                wrapped = np.maximum(np.maximum(lower - moved, moved - upper), 0.0)
                gap = np.minimum(gap, wrapped)
        return np.sqrt((gap * gap).sum(axis=1))

    def reaches(self, index: int, lower: Any, upper: Any, radius: float) -> bool:
        """Whether some point of the box ``lower``..``upper`` may lie within ``radius``.

        False only when none can: rounding is monotone, so no point of the box is nearer
        box ``index`` than ``distances`` finds for the box itself (NaN bounds: True).
        """
        lower, upper = np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)
        low, high = self._lower[index], self._upper[index]
        gap = np.maximum(np.maximum(low - upper, lower - high), 0.0)
        if self.torus:
            size = self._domain[1] - self._domain[0]
            for shift in (size, -size):
                wrapped = np.maximum(low - (upper + shift), (lower + shift) - high)
                gap = np.minimum(gap, np.maximum(wrapped, 0.0))
        return not float(np.sqrt((gap * gap).sum())) > radius * (1 + SLACK)

    def near(self, index: int, points: Any, radius: float) -> np.ndarray:
        """Whether each point lies within ``radius`` of box ``index``."""
        return self.distances(index, points) <= radius
