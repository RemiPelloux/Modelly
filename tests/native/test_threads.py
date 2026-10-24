"""The compiled modules under threads: on a free-threaded build these run truly in parallel.

Each test passes on every build; on a GIL build it checks the same invariants
with the threads interleaved by the interpreter instead.
"""

import sys
import sysconfig
import threading
from collections import Counter

import pytest

from modelly import Agent, Model
from modelly._native import cells, loops, sets
from modelly.core import rng
from modelly.core.rng import FastRandom
from modelly.space import CellAgent, OrthogonalMooreGrid

THREADS = 4
ROUNDS = 300


def run_threads(target, *args):
    """Start THREADS threads on ``target(index, barrier, *args)`` and join them."""
    barrier = threading.Barrier(THREADS)
    errors = []

    def guarded(index):
        try:
            target(index, barrier, *args)
        except BaseException as error:  # reported to the main thread
            errors.append(error)

    threads = [threading.Thread(target=guarded, args=(i,)) for i in range(THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []


@pytest.mark.skipif(
    not sysconfig.get_config_var("Py_GIL_DISABLED"), reason="not a free-threaded build"
)
def test_free_threaded_build_keeps_the_gil_off():
    """The compiled modules are active and importing them left the GIL off."""
    assert rng.NATIVE and cells.NATIVE and loops.NATIVE and sets.NATIVE
    assert not sys._is_gil_enabled()


@pytest.mark.parametrize("draw", ["randint", "choice", "sample", "shuffle"])
def test_shared_generator_draws_are_atomic(draw):
    """Draws from one generator by several threads give the serial draws, in some order."""
    items = list(range(50))
    calls = {
        "randint": lambda rng: rng.randint(0, 999),
        "choice": lambda rng: rng.choice(items),
        "sample": lambda rng: tuple(rng.sample(items, 3)),
        "shuffle": lambda rng: rng.shuffle(local := list(items)) or tuple(local),
    }
    call = calls[draw]
    serial_rng = FastRandom(42)
    serial = Counter(call(serial_rng) for _ in range(THREADS * ROUNDS))
    shared, results = FastRandom(42), [[] for _ in range(THREADS)]

    def work(index, barrier):
        barrier.wait()
        results[index].extend(call(shared) for _ in range(ROUNDS))

    run_threads(work)
    assert Counter(x for chunk in results for x in chunk) == serial
    assert shared.getstate() == serial_rng.getstate()


class Walker(CellAgent):
    """Moves to a random neighbouring cell and keeps a running total."""

    def step(self):
        """One move."""
        self.cell = self.cell.neighborhood.select_random_cell()
        self.total = getattr(self, "total", 0) + self.cell.coordinate[0]


def replicate(seed):
    """One independent run: a grid walk with select and agg every step."""
    model = Model(rng=seed)
    grid = OrthogonalMooreGrid((12, 12), torus=True, random=model.random)
    for _ in range(60):
        Walker(model).cell = grid.select_random_empty_cell()
    trace = []
    for _ in range(20):
        model.agents.shuffle_do("step")
        chosen = model.agents.select(lambda a: a.total % 2, at_most=0.5)
        trace.append((len(chosen), model.agents.agg("total", sum)))
    return trace


def test_replicates_on_threads_match_serial_runs():
    """Independent models on threads give exactly what they give one after the other."""
    seeds = [11, 12, 13, 14]
    serial = [replicate(seed) for seed in seeds]
    threaded = [None] * THREADS

    def work(index, barrier):
        barrier.wait()
        threaded[index] = replicate(seeds[index])

    run_threads(work)
    assert threaded == serial


def test_shared_grid_moves_keep_every_agent_in_one_cell():
    """Threads moving their own agents across shared cells lose and duplicate none."""
    model = Model(rng=5)
    grid = OrthogonalMooreGrid((6, 6), torus=True, random=model.random)
    spots = list(grid.all_cells)
    owned = [[CellAgent(model) for _ in range(10)] for _ in range(THREADS)]
    for agent in (a for group in owned for a in group):
        agent.cell = spots[0]

    def work(index, barrier):
        barrier.wait()
        for step in range(ROUNDS):
            for k, agent in enumerate(owned[index]):
                agent.cell = spots[(step * 7 + k * 3 + index) % len(spots)]

    run_threads(work)
    placed = Counter(agent for cell in spots for agent in cell._agents)
    everyone = [agent for group in owned for agent in group]
    assert placed == Counter(everyone)
    assert all(agent in agent.cell._agents for agent in everyone)


class Plain(Agent):
    """An agent with one attribute."""

    def __init__(self, model, value):
        """Keep the value."""
        super().__init__(model)
        self.value = value


def test_select_and_agg_while_other_threads_add_and_remove():
    """Readers of a shared set see consistent snapshots while writers change it."""
    model = Model(rng=9)
    for i in range(200):
        Plain(model, i)
    view = model.agents.select(lambda a: True)

    def work(index, barrier):
        barrier.wait()
        for step in range(ROUNDS):
            if index == 0:
                Plain(model, step).remove()
            subset = view.select(lambda a: a.value % 3 == 0, agent_type=Plain)
            assert all(a.value % 3 == 0 for a in subset)
            assert model.agents.agg("value", len) >= len(view) - 1
            view.shuffle(inplace=False).get("value")

    run_threads(work)
    assert len(view) == 200
