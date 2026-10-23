"""Tests for model.py."""

import numpy as np

from modelly.agent import Agent, AgentSet
from modelly.model import Model


def test_model_set_up():
    """Test Model initialization."""
    model = Model()
    assert model.running is True
    assert model.time == 0.0

    model.step()
    assert model.time == 1.0


def test_model_time_increment():
    """Test that time increments correctly with steps."""
    model = Model()

    for i in range(5):
        model.step()
        assert model.time == float(i + 1)


def test_running():
    """Test Model is running."""

    class TestModel(Model):
        def step(self):
            """Stop at step 10."""
            if self.time == 10:
                self.running = False

    model = TestModel()
    model.run_model()
    assert model.time == 10.0


def test_rng(rng=23):
    """Test initialization of model with specific seed."""
    model = Model(rng=rng)
    assert model.scenario.seed_sequence.entropy == rng
    model2 = Model(rng=rng + 1)
    assert model2.scenario.seed_sequence.entropy == rng + 1
    assert model.scenario.seed_sequence.entropy == rng

    assert Model(rng=42).random.random() == Model(rng=42).random.random()
    assert np.all(
        Model(rng=42).rng.random(
            10,
        )
        == Model(rng=42).rng.random(
            10,
        )
    )


def test_agent_types():
    """Test Model.agent_types property."""

    class TestAgent(Agent):
        pass

    model = Model()
    test_agent = TestAgent(model)
    assert test_agent in model.agents
    assert type(test_agent) in model.agent_types


def test_agents_by_type():
    """Test getting agents by type from Model."""

    class Wolf(Agent):
        pass

    class Sheep(Agent):
        pass

    model = Model()
    wolf = Wolf(model)
    sheep = Sheep(model)

    assert model.agents_by_type[Wolf] == AgentSet([wolf], random=model.random)
    assert model.agents_by_type[Sheep] == AgentSet([sheep], random=model.random)
    assert len(model.agents_by_type) == 2


def test_agent_remove():
    """Test removing all agents from the model."""

    class TestAgent(Agent):
        pass

    model = Model()
    for _ in range(100):
        TestAgent(model)
    assert len(model.agents) == 100

    model.remove_all_agents()
    assert len(model.agents) == 0


def test_agents_by_type_keeps_empty_bucket():
    """Removing all agents of a type keeps its empty bucket in agents_by_type.

    The per-type AgentSet is retained (as an empty set) after the last agent of
    that type is removed, and the type stays listed in agent_types. Models such
    as WolfSheep rely on this: they index agents_by_type[SomeType] every step and
    expect an empty set rather than a KeyError once that type goes extinct.
    """

    class Predator(Agent):
        pass

    class Prey(Agent):
        pass

    model = Model()
    for _ in range(3):
        Predator(model)
    for _ in range(2):
        Prey(model)

    for agent in list(model.agents_by_type[Prey]):
        agent.remove()

    assert Prey in model.agent_types
    assert len(model.agents_by_type[Prey]) == 0
    assert len(model.agents_by_type[Predator]) == 3


def test_inlined_registration_matches_register_agent():
    """Agent.__init__ inlines Model.register_agent; a subclass override must still be honoured."""
    from modelly import Agent  # noqa: PLC0415
    from modelly.experimental.signals import ModelSignals  # noqa: PLC0415

    seen = []

    class Watching(Model):
        def register_agent(self, agent):
            seen.append(("add", agent))
            super().register_agent(agent)

        def deregister_agent(self, agent):
            seen.append(("remove", agent))
            super().deregister_agent(agent)

    assert Model._default_registry is True
    assert Watching._default_registry is False
    watched = Watching(rng=1)
    a = Agent(watched)
    a.remove()
    assert seen == [("add", a), ("remove", a)]

    plain = Model(rng=1)
    signals = []

    def on_added(signal):  # handlers are held weakly, so keep named functions alive
        signals.append(("add", signal.additional_kwargs["args"][0]))

    def on_removed(signal):
        signals.append(("remove", signal.additional_kwargs["args"][0]))

    plain.observe("agents", ModelSignals.AGENT_ADDED, on_added)
    plain.observe("agents", ModelSignals.AGENT_REMOVED, on_removed)
    b = Agent(plain)
    assert b.unique_id == 1 and b in plain.agents and b in plain.agents_by_type[Agent]
    b.remove()
    assert b not in plain.agents and len(plain.agents) == 0
    assert signals == [("add", b), ("remove", b)]
