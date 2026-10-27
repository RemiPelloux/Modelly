"""Tests for the k-d partitioner of continuous spaces (modelly.distributed.kdtree)."""

import numpy as np
import pytest

from modelly.distributed import partition

SIDE = 10.0
BOUNDS = [[0.0, SIDE], [0.0, SIDE]]


def _points(n=1000, seed=0):
    """Uniform random points in the square."""
    return np.random.default_rng(seed).random((n, 2)) * SIDE


def _layout(parts, points=None, torus=False):
    """A layout of ``points`` (uniform by default) in ``parts`` boxes."""
    spec = partition.kd(parts)
    layout = spec.layout(points=_points() if points is None else points, bounds=BOUNDS)
    layout.torus = torus
    return layout


@pytest.mark.parametrize("parts", [1, 2, 3, 5, 8])
def test_boxes_hold_nearly_equal_populations(parts):
    """Every point has one owner and box populations differ by at most one or two."""
    points = _points()
    owners = _layout(parts, points).owners(points)
    counts = np.bincount(owners, minlength=parts)
    assert counts.sum() == len(points)
    assert counts.max() - counts.min() <= 2


def test_boxes_tile_the_domain():
    """The boxes' areas add up to the domain's, and each corner has an owner."""
    layout = _layout(6)
    area = sum(np.prod(np.subtract(b.upper, b.lower)) for b in layout.boxes)
    assert area == pytest.approx(SIDE * SIDE)
    corners = [(0, 0), (0, SIDE), (SIDE, 0), (SIDE, SIDE)]
    assert len(layout.owners(corners)) == len(corners)
    assert layout.owner((SIDE, SIDE)) in range(6)


def test_outside_points_are_refused():
    """A point outside the domain has no owner."""
    with pytest.raises(ValueError, match="outside"):
        _layout(4).owner((SIDE + 1, 0))


def test_near_is_a_superset_of_neighbours_of_the_box():
    """A point within ``radius`` of some point in box q is near q (brute force)."""
    points = _points(400, seed=4)
    radius = 0.7
    layout = _layout(4, points)
    owners = layout.owners(points)
    distances = np.linalg.norm(points[:, None] - points[None], axis=2)
    for box in range(4):
        close = (distances[:, owners == box] <= radius).any(axis=1)
        assert not (close & ~layout.near(box, points, radius)).any()


def test_torus_wraps_the_distance_to_a_box():
    """On a torus a point at one edge is near a box at the other edge."""
    points = np.array([[0.1, 5.0], [9.9, 5.0], [5.0, 5.0]] * 10)
    flat, torus = _layout(2, points), _layout(2, points, torus=True)
    left = flat.owner((0.1, 5.0))
    edge = np.array([[9.95, 5.0]])
    assert not flat.near(left, edge, 0.3)[0]
    assert torus.near(left, edge, 0.3)[0]


def test_layout_of_a_space_reads_its_positions(model_with_space):
    """``layout(space)`` uses the agents' positions and the space's bounds."""
    space = model_with_space.space
    layout = partition.kd(3).layout(space)
    owners = layout.owners(space.agent_positions)
    assert np.bincount(owners).tolist() == [10, 10, 10]
    assert layout.torus is space.torus


def test_bad_arguments_are_refused():
    """No boxes is refused."""
    with pytest.raises(ValueError, match="at least one"):
        partition.kd(0)


@pytest.fixture
def model_with_space():
    """A model with 30 agents in a torus continuous space."""
    from modelly import Model  # noqa: PLC0415
    from modelly.space.continuous.agents import ContinuousSpaceAgent  # noqa: PLC0415
    from modelly.space.continuous.space import ContinuousSpace  # noqa: PLC0415

    model = Model(rng=1)
    model.space = ContinuousSpace(BOUNDS, torus=True, random=model.random)
    for position in _points(30):
        ContinuousSpaceAgent(model.space, model).position = position
    return model
