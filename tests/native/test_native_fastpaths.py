"""The 1.5 fast paths of the C modules give exactly what their Python twins give."""

import random

import pytest

from modelly import Agent, Model
from modelly._native import cells, events, sets
from modelly.core.rng import NATIVE as RNG_NATIVE
from modelly.core.rng import FastRandom
from modelly.space import CellAgent, OrthogonalMooreGrid
from modelly.space.cells.cell import Cell
from modelly.time.events.event import Event


def handler():
    """An event callback."""


# --- fastset: live_refs, attr_values on a list changed by a getter ----------------


@pytest.mark.skipif(not sets.NATIVE, reason="fastset is not built")
def test_live_refs_keeps_the_live_refs_in_order():
    """The set's own refs (not new ones), dead ones left out."""
    model = Model(rng=1)
    agents = [Agent(model) for _ in range(12)]
    view = model.agents.select(lambda a: True)
    for agent in agents[::3]:
        agent.remove()
    del agent
    agents = [a for i, a in enumerate(agents) if i % 3]
    expected, got = sets.py_live_refs(view._refs), sets._fastset.live_refs(view._refs)
    assert got == expected
    assert all(a is b for a, b in zip(got, expected, strict=True))
    assert [r() for r in got] == agents
    with pytest.raises(TypeError):
        sets._fastset.live_refs([])


class Shrinker:
    """An attribute whose getter shortens or lengthens the list being read."""

    def __init__(self, items, grow):
        """Keep the list being read and whether to grow it."""
        self.items, self.grow = items, grow

    @property
    def value(self):
        """Pop the last item (or append a new one, a few times) and return an id."""
        if self.grow and len(self.items) < 12:
            self.items.append(Shrinker(self.items, self.grow))
        elif not self.grow and self.items:
            self.items.pop()
        return id(self)


@pytest.mark.skipif(not sets.NATIVE, reason="fastset is not built")
@pytest.mark.parametrize("grow", [False, True])
def test_attr_values_follows_a_list_changed_by_a_getter(grow):
    """A getter that shortens or lengthens the list reads as map() over the list does."""
    results = []
    for impl in (sets.py_attr_values, sets._fastset.attr_values):
        items = []
        items.extend(Shrinker(items, grow) for _ in range(6))
        results.append(
            [v == id(x) for v, x in zip(impl(items, "value"), items, strict=False)]
        )
        results.append(len(impl(items, "value")))
    assert results[0:2] == results[2:4]


# --- fastrng: sample with k=, choices --------------------------------------------


@pytest.mark.skipif(not RNG_NATIVE, reason="fastrng is not built")
@pytest.mark.parametrize("seed", range(40))
def test_sample_and_choices_match_the_standard_library(seed):
    """Keyword k, positional k, small and large k, lists and tuples: draw for draw."""
    population, small = list(range(100_000)), tuple(range(9))

    def script(r):
        return [
            r.sample(population, k=seed % 40),
            r.sample(population, seed % 7),
            r.sample(population, k=33),
            r.sample(small, k=seed % 9),
            r.choices(population, k=seed),
            r.choices(small),
            r.choices(small, k=-1),
            r.choices(small, [1] * 9, k=3),
            r.getstate(),
        ]

    assert script(FastRandom(seed)) == script(random.Random(seed))


@pytest.mark.skipif(not RNG_NATIVE, reason="fastrng is not built")
def test_choices_errors_and_overrides_match_the_standard_library():
    """Errors, and a subclass drawing with its own random(), as random.Random gives them."""

    def outcomes(cls):
        r, out = cls(3), []
        for call in (
            lambda: r.choices([], k=2),
            lambda: r.choices((), k=0),
            lambda: r.choices([1, 2], 2),
            lambda: r.choices([1, 2], k=1.5),
            lambda: r.sample([1, 2], k=5),
            lambda: r.sample([1, 2, 3], counts=[2, 1, 1], k=3),
        ):
            try:
                out.append(call())
            except (TypeError, ValueError, IndexError) as error:
                out.append((type(error), str(error)))
        return out

    assert outcomes(FastRandom) == outcomes(random.Random)

    class Low(FastRandom):
        def random(self):
            return super().random() / 3

    class LowStd(random.Random):
        def random(self):
            return super().random() / 3

    assert Low(5).choices(list(range(30)), k=20) == LowStd(5).choices(
        list(range(30)), k=20
    )


# --- fastcell: int capacity, equal agents, two cell types -------------------------


class Twin(CellAgent):
    """Agents that all compare equal: list.remove takes the first one."""

    def __eq__(self, other):
        """Every Twin equals every other Twin."""
        return isinstance(other, Twin)

    __hash__ = CellAgent.__hash__


class Annex(Cell):
    """A second cell type, inline like Cell."""


@pytest.mark.skipif(not cells.NATIVE, reason="fastcell is not built")
@pytest.mark.parametrize("capacity", [2, 2**70, -(2**70), None])
def test_moves_between_two_cell_types_with_equal_agents_match_python(capacity):
    """Same lists, same cells, same exceptions, for both setters."""
    results = []
    for move in (cells.py_set_cell, cells._fastcell.set_cell):
        model = Model(rng=3)
        grid = OrthogonalMooreGrid((3, 3), random=model.random)
        targets = [*list(grid.all_cells)[:3], Annex((7, 7), random=model.random)]
        for cell in targets:
            cell.capacity = capacity
        agents = [Twin(model) for _ in range(4)] + [CellAgent(model) for _ in range(2)]
        log = []
        for step in range(60):
            agent, target = agents[step % 6], targets[(step * 7) % 4]
            try:
                move(agent, target if step % 5 else None)
                log.append("ok")
            except Exception as error:  # the same exception either way
                log.append(type(error).__name__)
        index = {id(a): i for i, a in enumerate(agents)}
        results.append((log, [[index[id(a)] for a in c._agents] for c in targets]))
    assert results[0] == results[1]


# --- fastevents: ``in`` with Events that do and do not define == -------------------


class Same(Event):
    """An event equal to every other Same."""

    def __eq__(self, other):
        """Every Same equals every other Same."""
        return isinstance(other, Same)

    __hash__ = Event.__hash__


@pytest.mark.skipif(not events.NATIVE, reason="fastevents is not built")
def test_contains_matches_the_twin():
    """Identity for plain Events, == for an Event subclass that defines it."""
    plain = [Event(float(i), handler) for i in range(20)]
    same = [Same(1.0, handler), Same(2.0, handler)]
    queries = [plain[3], Event(1.0, handler), same[0], Same(5.0, handler), "x", None]
    for content in (plain, plain + same, same):
        heaps = (events.PyEventHeap(), events.EventHeap())
        for heap in heaps:
            for event in content:
                heap.push(event)
        assert [q in heaps[0] for q in queries] == [q in heaps[1] for q in queries]
