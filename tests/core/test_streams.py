"""Tests for per-agent random streams (Model.agent_streams)."""

import pickle

import numpy as np
import pytest

from modelly import Agent, Model
from modelly.core.rng import FastRandom
from modelly.scenarios import Scenario

SEED = 42
DRAWS = 5
POPULATION = 20
STEPS = 6


class Walker(Agent):
    """Records one stdlib and one numpy draw per step."""

    def __init__(self, model):
        """Start with no draws."""
        super().__init__(model)
        self.draws = []

    def step(self):
        """Draw from both of the agent's generators."""
        self.draws.append((self.random.random(), float(self.rng.random())))


class Shared(Model):
    """Walkers on the model's generators (the default)."""

    def __init__(self, rng=SEED, scenario=Scenario, n=POPULATION):
        """Create ``n`` walkers."""
        super().__init__(rng=rng, scenario=scenario)
        Walker.create_agents(self, n)

    def step(self):
        """Step the walkers in a random order."""
        self.agents.shuffle_do("step")


class Own(Shared):
    """Walkers with streams of their own."""

    agent_streams = True


def _draws(model):
    """Each walker's draws, by unique_id."""
    return {a.unique_id: a.draws for a in model.agents}


def _run(model, steps=STEPS):
    """Run ``model`` for ``steps`` and return it."""
    for _ in range(steps):
        model.step()
    return model


def test_off_by_default():
    """Without the flag, agents share the model's generators."""
    model = Shared()
    agent = next(iter(model.agents))
    assert agent.random is model.random
    assert agent.rng is model.rng


def test_each_agent_has_its_own_generators():
    """With the flag, each agent keeps one pair of generators of its own."""
    model = Own()
    first, second = list(model.agents)[:2]
    assert first.random is first.random
    assert first.rng is first.rng
    assert first.random is not model.random
    assert first.rng is not model.rng
    assert isinstance(first.random, FastRandom)
    assert type(first.rng.bit_generator) is type(model.rng.bit_generator)
    assert first.random.random() != second.random.random()


def test_draws_do_not_depend_on_activation_order():
    """Shuffled activation changes the order agents step, not what each one draws."""
    model = _run(Own())
    for agent in model.agents:
        fresh = Own()
        twin = next(a for a in fresh.agents if a.unique_id == agent.unique_id)
        for _ in range(STEPS):
            twin.step()
        assert twin.draws == agent.draws


def test_draws_do_not_depend_on_other_agents():
    """An agent draws the same numbers in a population of 1 or of 20."""
    alone = _run(Own(n=1))
    crowd = _run(Own())
    assert _draws(alone)[1] == _draws(crowd)[1]


def test_same_seed_same_streams_other_seed_other_streams():
    """The streams are a function of the model's seed."""
    assert _draws(_run(Own())) == _draws(_run(Own()))
    assert _draws(_run(Own())) != _draws(_run(Own(rng=SEED + 1)))


def test_replicates_get_different_streams():
    """Replicates spawned from one seed sequence draw differently."""
    root = np.random.SeedSequence(SEED)
    left, right = (Scenario(rng=np.random.default_rng(s)) for s in root.spawn(2))
    left_model, right_model = (
        Own(rng=None, scenario=left),
        Own(rng=None, scenario=right),
    )
    assert _draws(_run(left_model)) != _draws(_run(right_model))


def test_model_stream_untouched_by_agent_draws():
    """Agents drawing on their own streams leave the model's generators where they were."""
    model = Own()
    before = model.random.getstate()
    for agent in model.agents:
        agent.step()
    assert model.random.getstate() == before


def test_pickle_continues_each_stream():
    """A pickled model resumes every agent's stream draw for draw."""
    straight = _run(Own(), STEPS)
    half = _run(Own(), STEPS // 2)
    resumed = _run(pickle.loads(pickle.dumps(half)), STEPS - STEPS // 2)  # noqa: S301 - own data
    assert _draws(resumed) == _draws(straight)


def test_checkpoint_continues_each_stream(tmp_path):
    """Model.save and Model.load resume every agent's stream draw for draw."""
    straight = _run(Own(), STEPS)
    half = _run(Own(), STEPS // 2)
    half.save(tmp_path / "half.ckpt")
    resumed = _run(Own.load(tmp_path / "half.ckpt"), STEPS - STEPS // 2)
    assert _draws(resumed) == _draws(straight)


class Keyed(Walker):
    """Keys its stream on a label instead of the creation order."""

    def __init__(self, model, label):
        """Keep the label."""
        super().__init__(model)
        self.label = label

    def stream_key(self):
        """The label, whatever the creation order."""
        return self.label


def test_stream_key_makes_streams_independent_of_creation_order():
    """Agents keyed on a label draw the same whichever order they are created in."""
    forward, backward = Own(n=0), Own(n=0)
    for label in range(DRAWS):
        Keyed(forward, label)
    for label in reversed(range(DRAWS)):
        Keyed(backward, label)
    by_label = [
        {a.label: a.random.random() for a in m.agents} for m in (forward, backward)
    ]
    assert by_label[0] == by_label[1]


@pytest.mark.parametrize("key", [-1, 1.5, "a", None])
def test_invalid_stream_key_is_refused(key):
    """A stream key must be a non-negative int."""
    model = Own(n=0)
    agent = Keyed(model, key)
    with pytest.raises(ValueError, match="stream_key"):
        _ = agent.random
