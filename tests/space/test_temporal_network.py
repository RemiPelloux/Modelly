"""TemporalNetwork: lifetimes, incremental updates, rewinds, clocks and checkpoints."""

import math

import pytest

from modelly import Model
from modelly.space.networks import TemporalNetwork


def build():
    """Three edges with different lifetimes over nodes a, b, c."""
    network = TemporalNetwork(["a", "b", "c"])
    early = network.add_edge("a", "b", (0, 5))
    late = network.add_edge("b", "c", (3, math.inf), weight=2.0)
    again = network.add_edge("a", "b", (4, 8))
    return network, early, late, again


def test_edges_follow_their_lifetimes():
    """An edge is active on start <= time < end."""
    network, *_ = build()
    assert network.number_of_active_edges() == 0
    network.advance_to(0)
    assert network.neighbors("a") == ["b"] and network.neighbors("c") == []
    network.advance_to(3)
    assert sorted(network.neighbors("b")) == ["a", "c"]
    assert network.weighted_neighbors("b") == {"a": 1.0, "c": 2.0}
    network.advance_to(4.5)
    assert network.weighted_neighbors("a") == {"b": 2.0}  # two parallel edges
    assert network.degree("a") == 1
    network.advance_to(6)
    assert network.has_edge("a", "b") and network.has_edge("c", "b")
    network.advance_to(8)
    assert not network.has_edge("a", "b")
    assert list(network.active_edges()) == [("b", "c", 2.0)]


def test_updates_touch_only_changed_edges():
    """advance_to reports the number of edges switched on or off."""
    network = TemporalNetwork(1000)
    for i in range(999):
        network.add_edge(i, i + 1, (i, i + 2))
    assert network.advance_to(0) == 1
    assert network.advance_to(1) == 1  # one on, none off yet
    assert network.advance_to(2) == 2  # edge 2 on, edge 0 off
    assert network.advance_to(2) == 0
    assert network.number_of_active_edges() == 2


def test_rewind_replays_from_the_start():
    """Moving the clock back gives the same edges as moving forward to that time."""
    network, *_ = build()
    network.advance_to(10)
    network.advance_to(4.5)
    forward, *_ = build()
    forward.advance_to(4.5)
    assert list(network.active_edges()) == list(forward.active_edges())


def test_add_and_remove_at_current_time():
    """Edges added at a time already reached become active at once."""
    network, early, *_ = build()
    network.advance_to(1)
    network.add_edge("a", "d", (0, 2))
    assert "d" in network and network.neighbors("d") == ["a"]
    network.remove_edge(early)
    assert network.neighbors("a") == ["d"]
    network.advance_to(9)
    assert network.neighbors("d") == []
    with pytest.raises(ValueError):
        network.add_edge("a", "b", (3, 3))
    with pytest.raises(KeyError):
        network.neighbors("zz")


def test_directed_and_adjacency():
    """Directed edges are one-way; the adjacency matrix sums parallel weights."""
    network = TemporalNetwork(3, directed=True)
    network.add_edge(0, 1, weight=0.5)
    network.add_edge(0, 1, weight=0.25)
    network.add_edge(2, 2)
    network.advance_to(0)
    assert network.neighbors(1) == [] and network.neighbors(0) == [1]
    matrix = network.adjacency().toarray()
    assert matrix[0, 1] == 0.75 and matrix[1, 0] == 0 and matrix[2, 2] == 1.0


def test_clock_drives_queries_and_checkpoint(tmp_path):
    """With a model as clock, queries follow model.time, also after a load."""
    model = Model(rng=1)
    model.contacts = TemporalNetwork(["a", "b"], clock=model)
    model.contacts.add_edge("a", "b", (2, 4))
    assert model.contacts.neighbors("a") == []
    model.run_for(2)
    assert model.contacts.neighbors("a") == ["b"]
    model.save(tmp_path / "temporal.ckpt")
    restored = Model.load(tmp_path / "temporal.ckpt")
    assert restored.contacts.clock is restored
    restored.run_for(2)
    assert restored.contacts.neighbors("a") == []
