"""map_each and the weakref loops (AgentSet.do / shuffle_do / map) match their twins."""

import gc
import sys

import pytest

from modelly import Agent, Model
from modelly._native import loops
from modelly.core.agentset import AgentSet

pytestmark = pytest.mark.skipif(not loops.NATIVE, reason="fastloop is not built")
fastloop = loops._fastloop
STRONG = (loops.py_map_each, fastloop.map_each if loops.NATIVE else None)
WEAK = (
    (loops.py_call_each_weak, fastloop.call_each_weak if loops.NATIVE else None),
    (loops.py_map_each_weak, fastloop.map_each_weak if loops.NATIVE else None),
)


class Counter(Agent):
    """Records every call in a shared log and returns something."""

    def __init__(self, model, log):
        """Keep the shared log."""
        super().__init__(model)
        self.log = log

    def step(self):
        """Record a step."""
        self.log.append(("step", self.unique_id))
        return self.unique_id

    def hit(self, k, w=1, *, z=0):
        """Record a call with arguments."""
        self.log.append(("hit", self.unique_id, k, w, z))
        return k * w + z


def by_function(agent, k=0, **extra):
    """A callable taking the agent first."""
    agent.log.append(("fn", agent.unique_id, k, sorted(extra.items())))
    return agent.unique_id + k


CALLS = [
    ("step", (), None),
    ("hit", (3,), None),
    ("hit", (3,), {"w": 9}),
    ("hit", (3, 2), {"z": 5}),
    ("hit", (), {"z": 1, "k": 2, "w": 4}),
    (by_function, (), None),
    (by_function, (2,), {"q": 1, "r": 2}),
]


def fresh(n=25):
    """A model with ``n`` Counters sharing a log."""
    log = []
    model = Model(rng=5)
    return model, [Counter(model, log) for _ in range(n)], log


def twin_models(n=25):
    """The same population of Counters twice, each with its log."""
    return [fresh(n), fresh(n)]


@pytest.mark.parametrize(("method", "args", "kwargs"), CALLS)
def test_map_each_returns_the_same_results_in_order(method, args, kwargs):
    """Method names, callables, positional and keyword arguments."""
    outcomes = []
    for impl, (model, agents, log) in zip(STRONG, twin_models(), strict=True):
        order = list(agents)
        model.random.shuffle(order)
        outcomes.append((impl(order, model.agents, method, args, kwargs), log))
    assert outcomes[0] == outcomes[1]
    assert len(outcomes[1][0]) == 25


@pytest.mark.parametrize(("method", "args", "kwargs"), CALLS)
@pytest.mark.parametrize("pair", WEAK)
def test_weak_loops_make_the_same_calls(pair, method, args, kwargs):
    """The weakref versions call the same agents with the same arguments, in order."""
    outcomes = []
    for impl, (model, agents, log) in zip(pair, twin_models(), strict=True):
        view = AgentSet(agents, random=model.random)
        order = list(view._refs)
        model.random.shuffle(order)
        outcomes.append((impl(order, view._refs, method, args, kwargs), log))
    assert outcomes[0] == outcomes[1]
    assert len(outcomes[1][1]) == 25


@pytest.mark.parametrize("pair", WEAK)
def test_weak_loops_skip_agents_removed_or_collected_during_the_loop(pair):
    """An agent discarded from the set, or garbage collected, by an earlier call is skipped."""
    logs = []
    for impl in pair:
        model, agents, log = fresh(10)
        view = AgentSet(agents, random=model.random)
        first, discarded, doomed = agents[0], agents[1], [agents[3]]

        def act(
            agent, view=view, first=first, discarded=discarded, log=log, doomed=doomed
        ):
            log.append(agent.unique_id)
            if agent is first:
                view.discard(discarded)
                doomed.pop().remove()  # out of the model: the view's ref dies with it

        del agents
        impl(list(view._refs), view._refs, act, (), None)
        logs.append(log)
    assert logs[0] == logs[1]
    assert len(logs[1]) == 8


def test_weak_loops_propagate_exceptions_and_stop():
    """The first exception escapes; later agents are not called."""
    for impl in (*WEAK[0], *WEAK[1]):
        model = Model(rng=2)
        log = []
        agents = [Counter(model, log) for _ in range(5)]
        view = AgentSet(agents, random=model.random)

        def act(agent, agents=agents, log=log):
            log.append(agent)
            if agent is agents[2]:
                raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            impl(list(view._refs), view._refs, act, (), None)
        assert log == agents[:3]


def test_agentset_methods_match_the_pure_twins(monkeypatch):
    """AgentSet.do / shuffle_do / map and the strong map give what the twins give."""
    results = []
    for native in (True, False):
        if not native:
            from modelly.core.agentset import strong, weak  # noqa: PLC0415

            for module, name in (
                (weak, "call_each_weak"),
                (weak, "map_each_weak"),
                (strong, "map_each"),
            ):
                monkeypatch.setattr(module, name, getattr(loops, f"py_{name}"))
        log = []
        model = Model(rng=9)
        agents = [Counter(model, log) for _ in range(30)]
        view = AgentSet(agents, random=model.random)
        view.do("hit", 2, w=3)
        view.shuffle_do("step")
        mapped = (view.map("hit", 1, z=2), model.agents.map(by_function, k=1))
        results.append((log, mapped, model.random.random()))
    assert results[0] == results[1]


def test_wrong_argument_types_are_rejected():
    """Order a list, members a dict, args a tuple, kwargs a dict or None."""
    for func in (fastloop.map_each, fastloop.call_each_weak, fastloop.map_each_weak):
        with pytest.raises(TypeError):
            func((), {}, "step", (), None)
        with pytest.raises(TypeError):
            func([], [], "step", (), None)
        with pytest.raises(TypeError):
            func([], {}, "step", [], None)
        with pytest.raises(TypeError):
            func([], {}, "step", (), [("k", 1)])


def test_no_reference_leaks():
    """Repeated calls leave every reference count where it was, keyword values included."""
    model = Model(rng=3)
    agents = [Counter(model, []) for _ in range(5)]
    view = AgentSet(agents, random=model.random)
    value = object()
    before = [sys.getrefcount(a) for a in agents] + [sys.getrefcount(value)]
    for _ in range(1000):
        fastloop.map_each(list(agents), model.agents, by_function, (), {"q": value})
        fastloop.call_each_weak(
            list(view._refs), view._refs, by_function, (), {"q": value}
        )
        fastloop.map_each_weak(list(view._refs), view._refs, "step", (), None)
        for each in agents:
            each.log.clear()
    del each
    gc.collect()
    after = [sys.getrefcount(a) for a in agents] + [sys.getrefcount(value)]
    assert after == before
