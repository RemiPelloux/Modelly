"""Age-structured SEIR: the final-size relation, and same seed same run."""

import numpy as np
import pytest

from modelly.zoo.age_seir.model import AgeSEIR, SEIRScenario, State

POPULATION = 200_000
CONTACTS = 10.0
BETA = 0.035
RECOVERY = 0.2
SEEDS = (11, 12, 13)
# Five standard deviations of the final-size CLT: no fixed-seed run should get near it.
Z_BOUND = 5.0


def homogeneous(rng, groups=1, beta=BETA):
    """One population, mixing homogeneously, written as ``groups`` equal age groups."""
    size = POPULATION // groups
    contacts = np.full((groups, groups), CONTACTS / groups)
    return SEIRScenario(
        rng=rng,
        group_sizes=(size,) * groups,
        contacts=tuple(map(tuple, contacts)),
        beta=beta,
        recovery=RECOVERY,
        initial_infected=(20,) * groups,
        steps=600,
    )


def final_size_sd(model):
    """Standard deviation of the attack rate (Andersson and Britton's final-size CLT).

    ``sigma^2 = tau (1 - tau) (1 + cv^2 R0^2 (1 - tau)) / (1 - R0 (1 - tau))^2`` over the
    population size, with ``cv^2 = 1 - recovery`` for the geometric infectious period.
    """
    tau = float(model.final_size()[0])
    r0 = model.r0()
    cv2 = 1.0 - model.scenario.recovery
    escape = 1.0 - tau
    var = tau * escape * (1 + cv2 * r0**2 * escape) / (1 - r0 * escape) ** 2
    return np.sqrt(var / POPULATION)


@pytest.mark.parametrize("groups", [1, 3])
@pytest.mark.parametrize("seed", SEEDS)
def test_final_size_relation_homogeneous(groups, seed):
    """The simulated attack rate solves ``s = s0 exp(-R0 (1 - s))`` within the CLT bound."""
    model = AgeSEIR(homogeneous(seed, groups))
    model.run()
    assert model.counts()[:, [State.E, State.I]].sum() == 0  # the epidemic is over
    expected = model.final_size()
    simulated = model.counts()[:, State.R].sum() / POPULATION
    assert model.r0() == pytest.approx(CONTACTS * BETA / RECOVERY)
    assert np.allclose(expected, expected[0])
    assert abs(simulated - expected[0]) < Z_BOUND * final_size_sd(model)


def test_final_size_by_age_group():
    """With a heterogeneous matrix every group follows the multi-group relation."""
    model = AgeSEIR(SEIRScenario(rng=5, steps=800))
    model.run()
    assert model.r0() > 1
    # Each group has at least 20,000 people: 0.02 is many standard deviations.
    assert np.allclose(model.attack_rate(), model.final_size(), atol=0.02)
    # Children, with the most contacts, are hit hardest; seniors, with the fewest, least.
    assert list(np.argsort(model.final_size())) == [2, 1, 0]


def test_below_threshold_stays_small():
    """With R0 < 1 the outbreak dies out, as the final-size relation's only root says."""
    model = AgeSEIR(homogeneous(3, 1, beta=0.01))
    model.run()
    assert model.r0() < 1
    assert model.attack_rate()[0] < 0.01


def test_population_is_conserved():
    """Every transition moves people between rows; nobody appears or disappears."""
    model = AgeSEIR(SEIRScenario(rng=2, steps=60))
    model.run()
    assert np.array_equal(model.counts().sum(axis=1), model.sizes)
    frame = model.datacollector.get_model_vars_dataframe()
    assert (frame.sum(axis=1) == model.sizes.sum()).all()


def test_same_seed_same_run():
    """Same seed, same epidemic curve; another seed, another curve."""

    def curve(seed):
        model = AgeSEIR(SEIRScenario(rng=seed, steps=80))
        model.run()
        return model.datacollector.get_model_vars_dataframe()

    assert curve(4).equals(curve(4))
    assert not curve(4).equals(curve(5))
