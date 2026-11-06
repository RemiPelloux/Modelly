"""Caches behind the fast paths of the spaces: they must follow every change."""

import random

import numpy as np
import pytest

from modelly import Model
from modelly.space import Occupancy
from modelly.space.continuous import ContinuousSpace, ContinuousSpaceAgent
from modelly.space.delaunay import Delaunay
from modelly.space.networks import MultilayerNetwork


def test_reassigned_dimensions_move_the_bounds():
    """Assigning new dimensions recomputes the bounds in_bounds compares with."""
    space = ContinuousSpace([[0, 1], [0, 1]], random=random.Random(0))
    assert not space.in_bounds([2.0, 0.5])
    space.dimensions = [[0, 3], [0, 3]]
    assert space.in_bounds(np.array([2.0, 0.5]))
    assert not space.in_bounds(np.array([3.5, 0.5]))


def test_dimensions_are_read_only():
    """In-place edits cannot make the cached bounds stale."""
    dimensions = np.array([[0.0, 1.0], [0.0, 1.0]])
    space = ContinuousSpace(dimensions, random=random.Random(0))
    with pytest.raises(ValueError):
        space.dimensions[0, 1] = 5.0
    dimensions[0, 1] = 5.0  # the caller's array is copied, not shared
    assert not space.in_bounds(np.array([2.0, 0.5]))


def test_in_bounds_agrees_with_numpy_on_edges_and_odd_points():
    """The Python-float comparison gives numpy's answer."""
    space = ContinuousSpace([[0, 1], [-1, 0]], random=random.Random(0))
    low, high = space.dimensions[:, 0], space.dimensions[:, 1]
    for point in (
        [0.0, -1.0],
        [1.0, 0.0],
        [np.nan, -0.5],
        [0.5, 0.0 + 1e-300],
        [1.0 + 1e-16, 0.0],
    ):
        array = np.array(point)
        assert space.in_bounds(array) == bool(((array >= low) & (array <= high)).all())


def test_neighbors_in_radius_without_any_hit_is_empty():
    """Not even the agent itself within the radius: an empty answer."""
    model = Model(rng=0)
    space = ContinuousSpace([[0, 1], [0, 1]], random=model.random)
    agent = ContinuousSpaceAgent(space, model)
    agent.position = np.array([0.5, 0.5])
    agents, distances = agent.get_neighbors_in_radius(-1)
    assert agents == [] and distances.shape == (0,)


def test_multilayer_adjacency_follows_edges_weights_and_nodes():
    """The combined matrix cache is dropped on every change."""
    network = MultilayerNetwork(3, layers={"a": 1.0, "b": 2.0})
    network.add_edge(0, 1, "a")
    first = network.adjacency()
    first.data[:] = 99.0  # changing a returned matrix leaves the cache alone
    assert network.adjacency()[0, 1] == 1.0
    network.add_edge(1, 2, "b")
    assert network.adjacency()[1, 2] == 2.0
    network.add_layer("b", 3.0)
    assert network.adjacency()[1, 2] == 3.0
    network.remove_edge(0, 1, "a")
    assert network.adjacency()[0, 1] == 0.0
    network.add_node("new")
    assert network.adjacency().shape == (4, 4)


def test_occupancy_bounds_for_cells_beyond_the_rows():
    """Offsets answer cells outside the occupied range as searchsorted does."""
    occupancy = Occupancy(np.array([3, 0, 3, 70000]), n_cells=70001)
    start, end = occupancy.bounds(np.array([-5, 0, 1, 3, 69999, 70000, 70001, 10**9]))
    assert (end - start).tolist() == [0, 1, 0, 2, 0, 1, 0, 0]
    assert occupancy.order.tolist() == [1, 0, 2, 3]


def test_delaunay_from_a_pickle_without_float_circles():
    """The float circles are rebuilt when a triangulation lacks them."""
    triangulation = Delaunay()
    for point in ([1.0, 2.0], [3.0, 1.0], [2.0, 4.0]):
        triangulation.add_point(point)
    del triangulation._floats  # as pickled before the floats existed
    triangulation.add_point([2.5, 2.5])
    reference = Delaunay()
    for point in ([1.0, 2.0], [3.0, 1.0], [2.0, 4.0], [2.5, 2.5]):
        reference.add_point(point)
    assert list(triangulation.triangles.items()) == list(reference.triangles.items())
