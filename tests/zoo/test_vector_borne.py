"""Vector-borne transmission: outbreak sizes ordered by the Ross-Macdonald R0."""

import numpy as np
import pytest

from modelly.zoo.vector_borne.model import Host, Vector, VectorBorne, VectorScenario

# Vector densities giving R0 of about 0.5, 2 and 4 with the default bionomics.
DENSITIES = (0.5, 2.0, 4.0)
SEEDS = (1, 2, 3)
# Subcritical: the expected outbreak is about initial / (1 - R0) ~ 20 hosts, 1 % of 2000;
# 5 % is far beyond its spread.
SUBCRITICAL_ATTACK = 0.05


def outbreak(m, seed):
    """Run one outbreak to its end and return the model."""
    model = VectorBorne(VectorScenario(rng=seed, m=m))
    model.run()
    return model


def test_r0_is_linear_in_vector_density():
    """``R0 = m a^2 b c P / (recovery (1 - survival))``: doubling ``m`` doubles it."""
    r0 = [VectorBorne(VectorScenario(rng=0, m=m, steps=0)).r0() for m in DENSITIES]
    assert r0[0] < 1 < r0[1] < r0[2]
    assert np.allclose(np.array(r0) / np.array(DENSITIES), r0[0] / DENSITIES[0])
    s = VectorScenario()
    incubated = 0.9 * 0.1 / (1 - 0.9 * 0.9)
    expected = s.m * s.a**2 * s.b * s.c * incubated / (0.1 * 0.1)
    assert VectorBorne(VectorScenario(rng=0)).r0() == pytest.approx(expected)


@pytest.mark.parametrize("seed", SEEDS)
def test_attack_rates_follow_r0(seed):
    """For every seed the attack rates come out in the order of R0, small below one."""
    attack = [outbreak(m, seed).attack_rate() for m in DENSITIES]
    assert attack[0] < SUBCRITICAL_ATTACK
    # Above threshold the outbreak takes a large share; R0 = 4 far more than R0 = 2.
    assert attack[0] < attack[1] < attack[2]
    assert attack[2] > 0.8


def test_habitat_raster_confines_the_mosquitoes():
    """Cells without habitat have no mosquitoes; mosquito counts never go negative."""
    habitat = np.ones((10, 10))
    habitat[5:] = 0.0
    model = VectorBorne(VectorScenario(rng=4, habitat=habitat, steps=30))
    model.run()
    per_cell = np.bincount(
        model.vectors["cell"], weights=model.vectors["count"], minlength=100
    )
    assert per_cell[50:].sum() == 0
    assert per_cell[:50].sum() > 0
    assert (model.vectors["count"] >= 0).all()
    assert set(np.unique(model.vectors["state"])) <= {v.value for v in Vector}


def test_hosts_are_conserved():
    """Hosts move and change state but are never created or lost."""
    model = VectorBorne(VectorScenario(rng=2, steps=40))
    model.run()
    frame = model.datacollector.get_model_vars_dataframe()
    assert (frame.sum(axis=1) == 100 * 20).all()
    assert (model.hosts.row >= 0).all() and (model.hosts.row < 100).all()
    assert (model.hosts.state != Host.S).sum() >= model.scenario.initial_infected


def test_same_seed_same_run():
    """Same seed, same epidemic curve; another seed, another curve."""

    def curve(seed):
        model = VectorBorne(VectorScenario(rng=seed, steps=80))
        model.run()
        return model.datacollector.get_model_vars_dataframe()

    assert curve(5).equals(curve(5))
    assert not curve(5).equals(curve(6))
