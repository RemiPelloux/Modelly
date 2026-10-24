"""Tests for diff: first divergence in collected data and in agent state."""

import math

import numpy as np
import pytest
from timetravel_support import EXAMPLES

from modelly.timetravel import Difference, Recorder, RunDiff, agent_state, diff
from modelly.timetravel.snapshot import same

STEPS = 40
SEEDED_AT = 23


def recorded(name, perturb=None):
    """A recorded run of ``STEPS`` steps, ``perturb(model)`` at SEEDED_AT."""
    model = EXAMPLES[name]()
    with Recorder(model, every=10) as rec:
        model.run_for(SEEDED_AT)
        if perturb is not None:
            perturb(model)
            rec.checkpoint()
        model.run_for(STEPS - SEEDED_AT)
    return rec


def draw_once(model):
    """Consume one draw of each generator: a minimal seeded divergence."""
    model.random.random()
    model.rng.random()


@pytest.mark.parametrize("name", EXAMPLES)
def test_identical_runs(name):
    """Two runs from one seed have no difference, as models or recorders."""
    a, b = recorded(name), recorded(name)
    assert diff(a, b).identical
    result = diff(a.model, b.model)
    assert result.identical
    assert result.step is None
    assert str(result) == "The runs are identical."


@pytest.mark.parametrize("name", EXAMPLES)
def test_seeded_divergence_is_found_at_its_step(name):
    """One extra draw at step 23 is located at step 23 on every example."""
    result = diff(recorded(name), recorded(name, draw_once))
    assert not result.identical
    assert result.state.step == SEEDED_AT
    assert result.step == SEEDED_AT
    assert "diverge at step 23" in result.report()
    if result.data is not None:
        assert result.data.step > SEEDED_AT


def test_agent_and_attribute_are_named():
    """A changed agent attribute is reported with its agent and class."""

    def richer(model):
        agent = min(model.agents, key=lambda a: a.unique_id)
        agent.wealth += 1

    result = diff(recorded("boltzmann"), recorded("boltzmann", richer))
    found = result.state
    assert (found.step, found.agent, found.agent_class) == (23, 1, "MoneyAgent")
    assert (found.name, found.b) == ("wealth", found.a + 1)
    assert "agent 1 (MoneyAgent), wealth" in str(result)


def test_models_and_collected_data():
    """Models, collectors and DataFrames from other seeds diverge at step 0."""
    a, b = EXAMPLES["wolf_sheep"](), EXAMPLES["wolf_sheep"](seed=7)
    a.run_for(5)
    b.run_for(5)
    result = diff(a, b)
    assert result.data.step == 0
    assert result.state.step == 5
    assert diff(a.datacollector, b.datacollector).state is None
    frames = diff(
        a.datacollector.get_model_vars_dataframe(),
        b.datacollector.get_model_vars_dataframe(),
    )
    assert frames.data.step == 0
    assert frames.data.agent is None
    assert diff(a.datacollector, a.datacollector.get_model_vars_dataframe()).identical


def test_agent_records_and_collection_lengths():
    """Agent records name the agent; a shorter run differs where it stops."""
    a, b = EXAMPLES["boltzmann"](), EXAMPLES["boltzmann"]()
    a.run_for(6)
    b.run_for(4)
    result = diff(a.datacollector, b.datacollector)
    assert result.data == Difference(5.0, "collections", 7, 5)
    c = EXAMPLES["boltzmann"]()
    c.run_for(6)
    c.datacollector._agent_records[3.0][0] = (3.0, 1, 99)
    found = diff(a.datacollector, c.datacollector).data
    assert (found.step, found.agent, found.name, found.b) == (3.0, 1, "Wealth", 99)


def test_bad_input_is_refused():
    """Only models, recorders, collectors and DataFrames can be diffed."""
    with pytest.raises(TypeError, match="Cannot diff"):
        diff(EXAMPLES["boltzmann"](), [1, 2])


def test_snapshot_values():
    """Snapshots keep scalars, short vectors and places; NaN equals NaN."""
    model = EXAMPLES["boids"]()
    boid = next(iter(model.agents))
    state = agent_state(boid)
    assert isinstance(state["direction"], tuple)
    assert len(state["position"]) == 2
    assert "neighbors" not in state
    assert same(math.nan, math.nan)
    assert same(np.arange(3), np.arange(3))
    assert not same(np.arange(3), np.arange(4))
    assert RunDiff().identical
    who = Difference(1.0, "x", 1, 2, agent=4)
    assert str(who) == "step 1, agent 4, x: 1 != 2"
