"""Causal analysis: effects with common random numbers, attribution, counterfactuals, Shapley."""

import numpy as np
import pytest

from modelly.decide import model_runner
from modelly.examples.basic.virus_on_network.agents import State
from modelly.examples.basic.virus_on_network.model import VirusOnNetwork
from modelly.explain import attribute, counterfactual, shapley, treatment_effect
from modelly.timetravel import Recorder
from modelly.zoo.bass_diffusion.model import BassDiffusion, BassScenario

BASS = model_runner(BassDiffusion, {"adoption": lambda m: m.adoption}, scenario=BassScenario,
                    base={"steps": 60})  # fmt: skip


def test_common_random_numbers_shrink_the_variance_of_an_effect():
    """Raising imitation from 0.38 to 0.40: same effect, many times less variance paired."""
    effect = treatment_effect(
        BASS, {}, {"imitation": 0.40}, "adoption", replicates=20, seed=1
    )
    assert 0.015 < effect.mean < 0.025 and effect.low > 0
    assert effect.variance_reduction > 10
    again = treatment_effect(
        BASS, {}, {"imitation": 0.40}, "adoption", replicates=20, seed=1
    )
    assert again == effect


def outbreak(seed):
    """Sixty people on a contact network, one of them infected."""
    return VirusOnNetwork(
        num_nodes=60, avg_node_degree=3, initial_outbreak_size=1, rng=seed
    )


def ever_infected(model):
    """People who caught the virus at some point."""
    return sum(agent.state != State.SUSCEPTIBLE for agent in model.agents)


def immunise(model, agent):
    """Make one agent resistant from the start."""
    agent.state = State.RESISTANT


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_attribution_finds_patient_zero(seed):
    """Of sixty people, immunising the index case changes the outbreak most, by far."""
    found = attribute(outbreak, lambda m: list(m.agents), ever_infected, steps=40,
                      seeds=[seed], intervene=immunise)  # fmt: skip
    index_case = [
        a.unique_id for a in outbreak(seed).agents if a.state == State.INFECTED
    ]
    assert found.top(1) == index_case
    effects = found.table["effect"].to_numpy()
    assert effects[0] > 3 * effects[1]


def test_a_counterfactual_replays_a_recorded_run_with_a_change():
    """Curing everyone at step 3 of a recorded outbreak: fewer infections at step 30."""
    model = outbreak(4)
    with Recorder(model, every=1) as recorder:
        model.run_for(30)

    def cure(m):
        for agent in m.agents:
            if agent.state == State.INFECTED:
                agent.state = State.RESISTANT

    one = counterfactual(recorder, 3, cure, 30, ever_infected)
    assert one.mean < 0 and one.replicates == 1
    many = counterfactual(recorder, 3, cure, 30, ever_infected, branches=8)
    assert many.high < 0 and many.replicates == 8
    unchanged = counterfactual(
        recorder, 3, lambda m: None, 30, ever_infected, branches=4
    )
    assert unchanged.mean == 0 and unchanged.paired_variance == 0


def test_shapley_values_are_exact_and_add_up():
    """Linear: w_j (x_j - mean_j); any function: the values sum to f(x) - E f(background)."""
    rng = np.random.default_rng(0)
    background = rng.random((200, 3))
    weights = np.array([2.0, -1.0, 0.5])
    point = np.array([0.9, 0.2, 0.5])
    linear = shapley(lambda u: u @ weights, point, background, ["a", "b", "c"])
    expected = weights * (point - background.mean(axis=0))
    np.testing.assert_allclose(list(linear.values()), expected)

    def bumpy(u):
        return np.sin(3 * u[:, 0]) * u[:, 1] + u[:, 2] ** 2

    values = shapley(bumpy, point, background)
    total = bumpy(point[None])[0] - bumpy(background).mean()
    assert sum(values.values()) == pytest.approx(total)
    with pytest.raises(ValueError, match="parameters"):
        shapley(bumpy, point, background[:, :2])
