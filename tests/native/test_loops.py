"""The compiled loops give exactly what their Python twins give."""

import sys

import numpy as np
import pytest

from modelly import Agent, Model
from modelly._native import loops
from modelly.space import (
    HexGrid,
    Network,
    OrthogonalMooreGrid,
    OrthogonalVonNeumannGrid,
)

pytestmark = pytest.mark.skipif(not loops.NATIVE, reason="fastloop is not built")
fastloop = loops._fastloop


def grids():
    """Spaces with different connection patterns, edges and wraps."""
    model = Model(rng=7)
    networkx = pytest.importorskip("networkx")
    yield OrthogonalMooreGrid((9, 7), torus=False, random=model.random)
    yield OrthogonalMooreGrid((6, 6), torus=True, random=model.random)
    yield OrthogonalVonNeumannGrid((8, 5), torus=False, random=model.random)
    yield HexGrid((8, 6), torus=True, random=model.random)
    yield Network(networkx.barabasi_albert_graph(40, 2, seed=3), random=model.random)


@pytest.mark.parametrize("radius", [1, 2, 3, 5, 50, np.int64(4)])
def test_neighborhood_matches_python_order_and_values(radius):
    """Same cells, same order, the same live agent lists."""
    for space in grids():
        for cell in list(space.all_cells)[::3]:
            expected = loops.py_neighborhood(cell, radius)
            got = fastloop.neighborhood(cell, radius)
            assert list(got) == list(expected)
            assert all(got[c] is expected[c] for c in got)


def test_neighborhood_rejects_a_non_integer_radius():
    """A float radius fails the way range() does."""
    model = Model(rng=1)
    cell = next(iter(OrthogonalMooreGrid((3, 3), random=model.random).all_cells))
    with pytest.raises(TypeError):
        fastloop.neighborhood(cell, 2.5)


class Counter(Agent):
    """Records every call in a shared log."""

    def __init__(self, model, log):
        """Keep the shared log."""
        super().__init__(model)
        self.log = log

    def step(self):
        """Record a step."""
        self.log.append(("step", self.unique_id))

    def hit(self, k, w=1):
        """Record a call with arguments."""
        self.log.append(("hit", self.unique_id, k, w))


def run_both(method, args=(), kwargs=None, n=25):
    """Run the same call through both implementations on twin models."""
    logs = []
    for impl in (loops.py_call_each, fastloop.call_each):
        log = []
        model = Model(rng=5)
        for _ in range(n):
            Counter(model, log)
        order = list(model.agents)
        model.random.shuffle(order)
        impl(order, model.agents, method, args, kwargs)
        logs.append(log)
    return logs


@pytest.mark.parametrize(
    ("method", "args", "kwargs"),
    [
        ("step", (), None),
        ("hit", (3,), None),
        ("hit", (3,), {"w": 9}),
        (lambda agent, k=0: agent.log.append(("fn", agent.unique_id, k)), (), None),
        (lambda agent, k=0: agent.log.append(("fn", agent.unique_id, k)), (), {"k": 2}),
    ],
)
def test_call_each_makes_the_same_calls_in_the_same_order(method, args, kwargs):
    """Method names, callables, positional and keyword arguments."""
    python_log, native_log = run_both(method, args, kwargs)
    assert native_log == python_log
    assert len(native_log) == 25


def test_call_each_skips_agents_removed_during_the_loop():
    """An agent removed by an earlier call is not called."""
    model = Model(rng=2)
    log = []
    agents = [Counter(model, log) for _ in range(10)]
    victims = set(agents[1::2])

    def act(agent):
        log.append(agent)
        if agent is agents[0]:
            for victim in victims:
                victim.remove()

    fastloop.call_each(list(agents), model.agents, act, (), None)
    assert log == [a for a in agents if a not in victims]


def test_call_each_propagates_exceptions_and_stops():
    """The first exception escapes; later agents are not called."""
    model = Model(rng=2)
    log = []
    agents = [Counter(model, log) for _ in range(5)]

    def act(agent):
        log.append(agent)
        if agent is agents[2]:
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        fastloop.call_each(list(agents), model.agents, act, (), None)
    assert log == agents[:3]


def test_call_each_rejects_wrong_argument_types():
    """Order must be a list, members a dict and args a tuple."""
    with pytest.raises(TypeError):
        fastloop.call_each((), {}, "step", (), None)
    with pytest.raises(TypeError):
        fastloop.call_each([], {}, "step", [], None)


def test_no_reference_leaks():
    """Repeated calls leave every reference count where it was."""
    model = Model(rng=3)
    agents = [Counter(model, []) for _ in range(5)]
    cell = next(iter(OrthogonalMooreGrid((5, 5), random=model.random).all_cells))
    before = [sys.getrefcount(a) for a in agents] + [sys.getrefcount(cell)]
    for _ in range(1000):
        fastloop.call_each(list(agents), model.agents, "step", (), None)
        fastloop.neighborhood(cell, 2)
    after = [sys.getrefcount(a) for a in agents] + [sys.getrefcount(cell)]
    assert after == before
