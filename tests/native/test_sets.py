"""The compiled AgentSet loops give exactly what their Python twins give."""

import gc
import sys
import weakref

import pytest

from modelly import Agent, Model
from modelly._native import sets
from modelly.core.agentset import attributes, selection, weak

pytestmark = pytest.mark.skipif(not sets.NATIVE, reason="fastset is not built")
fastset = sets._fastset
PAIRS = ("keep_type", "keep_if", "attr_values", "live_agents", "make_refs")


class Walker(Agent):
    """An agent with a value and a nested position."""

    def __init__(self, model, value):
        """Keep the value and a position object."""
        super().__init__(model)
        self.value = value
        self.pos = type("P", (), {"x": value * 2})()


class Runner(Walker):
    """A subclass, for the type filter."""


def population(n=30):
    """A model with mixed agent types and its agents in order."""
    model = Model(rng=4)
    agents = [(Runner if i % 3 == 0 else Walker)(model, i) for i in range(n)]
    return model, agents


def both(name, *args):
    """Call the twin and the compiled function with the same arguments."""
    return getattr(sets, f"py_{name}")(*args), getattr(fastset, name)(*args)


@pytest.mark.parametrize("n", [0, 1, 30])
def test_keep_type_and_keep_if_match(n):
    """Same agents, same order, for empty, single and mixed lists."""
    _, agents = population(n)
    for cls in (Agent, Walker, Runner, (Runner, int), int):
        expected, got = both("keep_type", agents, cls)
        assert got == expected
    for func in (
        lambda a: a.value % 2,
        lambda a: a.value > 10,
        bool,
        lambda a: [] if a else 1,
    ):
        expected, got = both("keep_if", agents, func)
        assert got == expected


def test_keep_if_calls_once_per_agent_in_order():
    """The filter sees every agent once, in list order."""
    _, agents = population()
    logs = []
    for impl in (sets.py_keep_if, fastset.keep_if):
        log = []
        impl(agents, lambda a, log=log: log.append(a.unique_id) or True)
        logs.append(log)
    assert logs[0] == logs[1] == [a.unique_id for a in agents]


def test_keep_if_propagates_the_first_exception():
    """An exception stops the loop at the same agent in both versions."""
    _, agents = population()

    def func(agent, seen):
        seen.append(agent)
        if agent.value == 7:
            raise RuntimeError("boom")
        return True

    for impl in (sets.py_keep_if, fastset.keep_if):
        seen = []
        with pytest.raises(RuntimeError, match="boom"):
            impl(agents, lambda a, seen=seen: func(a, seen))
        assert seen == agents[:8]


def test_attr_values_match_including_dotted_names():
    """Plain and dotted names read as operator.attrgetter reads them."""
    _, agents = population()
    for name in ("value", "pos.x", "unique_id"):
        expected, got = both("attr_values", agents, name)
        assert got == expected


@pytest.mark.parametrize(
    ("name", "error"), [("missing", AttributeError), (3, TypeError)]
)
def test_attr_values_raise_the_same_exceptions(name, error):
    """A missing attribute and a non-str name fail the same way."""
    _, agents = population(3)
    for impl in (sets.py_attr_values, fastset.attr_values):
        with pytest.raises(error):
            impl(agents, name)


def test_live_agents_skips_dead_refs_in_order():
    """Collected agents are left out, the others stay in insertion order."""
    model, agents = population()
    view = model.agents.select(lambda a: True)
    for agent in agents[::4]:
        agent.remove()
    doomed = agents[::4]
    del agents
    expected, got = both("live_agents", dict(view._refs))
    assert got == expected
    del doomed
    gc.collect()
    expected, got = both("live_agents", view._refs)
    assert got == expected


def test_make_refs_matches_and_keeps_callbacks():
    """Same keys in the same order; each ref calls back on collection."""
    _, agents = population()
    calls = []
    expected, got = both("make_refs", agents + agents[:3], calls.append)
    assert list(got) == list(expected)
    assert [r() for r in got] == agents
    assert set(got.values()) == {None}
    with pytest.raises(TypeError):
        fastset.make_refs([1], calls.append)
    with pytest.raises(TypeError):
        fastset.make_refs(3, calls.append)


def test_wrong_argument_types_are_rejected():
    """Lists where lists are required, a dict for live_agents."""
    with pytest.raises(TypeError):
        fastset.keep_if((1,), bool)
    with pytest.raises(TypeError):
        fastset.keep_type([], int, int)
    with pytest.raises(TypeError):
        fastset.live_agents([])


def test_no_reference_leaks():
    """Repeated calls leave every reference count where it was."""
    model, agents = population(10)
    view = model.agents.select(lambda a: True)
    before = [sys.getrefcount(a) for a in agents]
    for _ in range(1000):
        fastset.keep_type(agents, Runner)
        fastset.keep_if(agents, bool)
        fastset.attr_values(agents, "pos.x")
        fastset.live_agents(view._refs)
        fastset.make_refs(agents, None)
    assert [sys.getrefcount(a) for a in agents] == before
    assert all(isinstance(r, weakref.ref) for r in view._refs)


def test_select_and_agg_are_identical_with_and_without_c(monkeypatch):
    """The AgentSet methods give the same answers on the pure twins."""
    model, _ = population(40)
    native = (
        model.agents.select(
            lambda a: a.value % 3, agent_type=Walker, at_most=9
        ).to_list(),
        model.agents.agg("value", [sum, max]),
        model.agents.select(lambda a: True).agg("pos.x", sum),
    )
    for module in (attributes, selection, weak):
        for name in PAIRS:
            if hasattr(module, name):
                monkeypatch.setattr(module, name, getattr(sets, f"py_{name}"))
    pure = (
        model.agents.select(
            lambda a: a.value % 3, agent_type=Walker, at_most=9
        ).to_list(),
        model.agents.agg("value", [sum, max]),
        model.agents.select(lambda a: True).agg("pos.x", sum),
    )
    assert native == pure
