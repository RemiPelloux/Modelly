"""Tests for modelly.profile.Profiler: what it records, and that it leaves no trace."""

import pytest

from modelly import Agent, DataCollector, Model
from modelly._native import loops
from modelly.core.agentset import AgentSet, _HardKeyAgentSet
from modelly.core.agentset import strong as strong_module
from modelly.examples.advanced.wolf_sheep.model import WolfSheep, WolfSheepScenario
from modelly.examples.basic.boltzmann_wealth_model.model import (
    BoltzmannScenario,
    BoltzmannWealth,
)
from modelly.profile import Profiler, StepRecord
from modelly.profile.hints import growth_exponent, hints
from modelly.profile.report import profiled_wall, rows
from modelly.time.events.event import Event

PATCHED = [
    (cls, name)
    for cls in (_HardKeyAgentSet, AgentSet)
    for name in ("do", "shuffle_do", "map")
]
PATCHED += [(DataCollector, "collect"), (Event, "execute")]


class Walker(Agent):
    """Draws from the model's generator and sometimes dies or gives birth."""

    def step(self):
        """Maybe die, maybe give birth."""
        roll = self.random.random()
        if roll < 0.1:
            self.remove()
        elif roll > 0.85:
            Walker(self.model)

    def score(self):
        """A value for map."""
        return self.unique_id


class Busy(Model):
    """Walkers, a collector, a one-off and a recurring event."""

    def __init__(self, n=50, rng=None):
        """Create the walkers, the collector and the event."""
        super().__init__(rng=rng)
        Walker.create_agents(self, n)
        self.collector = DataCollector(model_reporters={"n": lambda m: len(m.agents)})
        self.ticks = 0
        self.schedule_event(self.tick, at=2.5)

    def tick(self):
        """The one-off event."""
        self.ticks += 1

    def step(self):
        """Run every kind of loop and collect."""
        self.agents.shuffle_do("step")
        self.agents.select(lambda a: a.unique_id % 2).do("score")
        self.agents.map(Walker.score)
        self.collector.collect(self)


class Scanner(Agent):
    """Looks at every other agent: O(N) per agent."""

    def step(self):
        """Count every other agent."""
        self.seen = sum(1 for other in self.model.agents if other is not self)


class Crowd(Model):
    """A population of scanners that grows every step."""

    def __init__(self, rng=None):
        """Start with 50 scanners."""
        super().__init__(rng=rng)
        Scanner.create_agents(self, 50)

    def step(self):
        """Scan, then grow by half."""
        self.agents.do("step")
        Scanner.create_agents(self, len(self.agents) // 2)


class Broken(Model):
    """Raises at time 3."""

    def step(self):
        """Fail at time 3."""
        if self.time >= 3:
            raise RuntimeError("boom")


def originals():
    """What the patched names hold in their class dicts right now."""
    return [cls.__dict__.get(name) for cls, name in PATCHED]


def test_records_steps_loops_collect_and_events():
    """Each step records its loops, collect calls and the events after it."""
    model = Busy(rng=3)
    with Profiler(model) as prof:
        model.run_for(5)
    assert [r.step for r in prof.records] == [1, 2, 3, 4, 5]
    assert [r.time for r in prof.records] == [1.0, 2.0, 3.0, 4.0, 5.0]
    first = prof.records[0]
    assert first.agents == 50
    assert first.wall > 0 and first.cpu >= 0
    kinds = {key[0] for key in first.ops}
    assert {"shuffle_do", "do", "map", "collect"} <= kinds
    calls, agents, _, _ = first.ops[("shuffle_do", "Walker", "step")]
    assert (calls, agents) == (1, 50)
    assert ("map", "Walker", "Walker.score") in first.ops
    assert ("event", "", "Busy.tick") in prof.records[1].ops  # 2.5 runs after step 2
    assert model.ticks == 1


def test_births_and_deaths_add_up_to_the_population_change():
    """Births minus deaths is the change in population between steps."""
    model = Busy(rng=5)
    with Profiler(model) as prof:
        model.run_for(10)
    for record, after in zip(prof.records, prof.records[1:]):
        assert record.agents + record.births - record.deaths == after.agents
    last = prof.records[-1]
    assert last.agents + last.births - last.deaths == len(model.agents)
    assert sum(r.births for r in prof.records) > 0
    assert sum(r.deaths for r in prof.records) > 0


def test_sample_every_profiles_one_step_in_n():
    """Steps 1, 1 + N, ... are recorded; N must be positive."""
    model = Busy(rng=1)
    with Profiler(model, sample_every=3) as prof:
        model.run_for(10)
    assert [r.step for r in prof.records] == [1, 4, 7, 10]
    with pytest.raises(ValueError):
        Profiler(model, sample_every=0)


def run_seeded(model_factory, profiled):
    """The collected data and generator states of a seeded run."""
    model = model_factory()
    if profiled:
        with Profiler(model):
            model.run_for(20)
    else:
        model.run_for(20)
    frame = model.datacollector.get_model_vars_dataframe()
    return frame, model.random.random(), model.rng.random()


@pytest.mark.parametrize("pure", [False, True])
@pytest.mark.parametrize(
    "factory",
    [
        lambda: WolfSheep(WolfSheepScenario(rng=42)),
        lambda: BoltzmannWealth(BoltzmannScenario(rng=7, n=200)),
    ],
)
def test_profiling_does_not_change_results(factory, pure, monkeypatch):
    """Same data and generator states with and without the profiler."""
    if pure:
        monkeypatch.setattr(strong_module, "call_each", loops.py_call_each)
    plain = run_seeded(factory, profiled=False)
    profiled = run_seeded(factory, profiled=True)
    assert plain[0].equals(profiled[0])
    assert plain[1:] == profiled[1:]


def test_originals_are_restored_exactly_on_exit():
    """The class dicts hold the very same objects after the block."""
    before = originals()
    model = Busy(rng=2)
    with Profiler(model):
        assert originals() != before
    assert all(a is b for a, b in zip(originals(), before, strict=True))
    assert Profiler._active is None


def test_originals_are_restored_when_the_run_raises():
    """A failing run restores the originals and keeps its records."""
    before = originals()
    model = Broken(rng=0)
    with pytest.raises(RuntimeError, match="boom"), Profiler(model) as prof:
        model.run_for(5)
    assert all(a is b for a, b in zip(originals(), before, strict=True))
    assert Profiler._active is None
    assert [r.step for r in prof.records] == [1, 2, 3]
    assert prof.records[-1].wall > 0


def test_only_one_profiler_at_a_time():
    """A second profiler cannot start while one runs."""
    model = Busy(rng=0)
    with Profiler(model), pytest.raises(RuntimeError, match="already active"):
        Profiler(model).__enter__()
    assert Profiler._active is None


def test_report_table_and_dataframe():
    """The text table, the DataFrame and the dict agree on the run."""
    model = Busy(rng=4)
    with Profiler(model) as prof:
        model.run_for(4)
    text = prof.report(top=2)
    assert text.startswith("Busy: 4 step(s) profiled")
    assert "Walker.step (shuffle_do)" in text
    assert "more operation(s)" in text
    frame = prof.to_dataframe()
    assert (frame["kind"] == "step").sum() == 4
    assert set(frame["kind"]) >= {"step", "shuffle_do", "collect"}
    data = prof.to_dict()
    assert data["model"] == "Busy" and len(data["steps"]) == 4
    assert data["operations"][0]["wall_s"] >= data["operations"][-1]["wall_s"]


def test_report_without_steps():
    """A profiler that saw no step reports so."""
    prof = Profiler(Busy(rng=0))
    assert "no step was profiled" in prof.report()
    assert prof.to_dataframe().empty
    assert prof.to_dict()["hints"] == []


def test_growing_scan_points_at_mdl101():
    """A per-agent cost growing with N points at MDL101."""
    model = Crowd(rng=0)
    with Profiler(model) as prof:
        model.run_for(8)
    text = prof.report()
    assert "MDL101" in text
    assert "Scanner.step (do)" in text


def test_hand_written_loop_points_at_mdl103():
    """A step that runs agents outside AgentSet loops points at MDL103."""

    class ByHand(Model):
        def __init__(self):
            """Fifty scanners."""
            super().__init__(rng=0)
            Scanner.create_agents(self, 50)

        def step(self):
            """Step the agents in a for loop."""
            for agent in list(self.agents):
                agent.step()

    model = ByHand()
    with Profiler(model) as prof:
        model.run_for(3)
    assert "MDL103" in prof.report()


def test_heavy_collect_hint():
    """A collect taking most of the time points at columns."""
    model = Busy(rng=0)
    with Profiler(model) as prof:
        model.run_for(3)
    record = prof.records[0]
    record.ops[("collect", "DataCollector", "collect")][2] = record.wall * 10
    found = hints(prof.records, rows(prof.records), profiled_wall(prof.records))
    assert any("Column" in hint for hint in found)


def test_growth_exponent_from_synthetic_records():
    """Cost per agent proportional to N gives a slope of 1; a fixed N gives None."""
    key = ("do", "A", "step")

    def record(n, us_per_agent):
        step = StepRecord(1, 1.0, n)
        step.ops[key] = [1, n, n * us_per_agent / 1e6, 0.0]
        return step

    growing = [record(n, n * 0.01) for n in (100, 200, 400, 800)]
    assert growth_exponent(growing, key) == pytest.approx(1.0)
    flat = [record(500, 2.0) for _ in range(5)]
    assert growth_exponent(flat, key) is None
    assert growth_exponent(growing[:2], key) is None
