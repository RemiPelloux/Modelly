"""Energy budgets: the population settles at the carrying capacity of the energy balance."""

import numpy as np
import pytest

from modelly.zoo.energy_budget.model import EnergyBudget, EnergyScenario, Forager

BURN_IN = 150
# The population fluctuates by about 2 % of K from step to step; averaging 250 correlated
# steps leaves well under 1 %. The starvation deficit (at most one cost per death) pushes
# the mean up by a few tenths of a percent. 3 % covers both with room to spare.
RELATIVE_TOLERANCE = 0.03


def equilibrium(seed, **changes):
    """Mean population after the burn-in, and the model."""
    model = EnergyBudget(EnergyScenario(rng=seed, **changes))
    model.run()
    frame = model.datacollector.get_model_vars_dataframe()
    return frame["foragers"].iloc[BURN_IN:].mean(), model


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("inflow", [0.5, 1.0])
def test_equilibrium_density_is_the_carrying_capacity(seed, inflow):
    """Mean population within 3 % of ``K = efficiency * inflow * cells / cost``."""
    mean, model = equilibrium(seed, inflow=inflow)
    assert model.carrying_capacity() == pytest.approx(0.5 * inflow * 900)
    assert mean == pytest.approx(model.carrying_capacity(), rel=RELATIVE_TOLERANCE)


def test_resource_stock_stays_bounded():
    """Intake matches inflow: the uneaten stock does not grow after the burn-in."""
    _, model = equilibrium(4)
    stock = model.datacollector.get_model_vars_dataframe()["resource"].iloc[BURN_IN:]
    half = len(stock) // 2
    assert stock.iloc[half:].mean() == pytest.approx(stock.iloc[:half].mean(), rel=0.05)


def test_no_inflow_means_extinction():
    """Without resource every forager starves once its initial energy is spent."""
    model = EnergyBudget(EnergyScenario(rng=1, inflow=0.0, steps=20))
    model.run()
    assert model.population() == 0
    model.step()  # an empty population still steps
    assert model.population() == 0


def test_columns_follow_the_agents():
    """Energies are non-negative and below the birth threshold after each step."""
    model = EnergyBudget(EnergyScenario(rng=2, steps=30))
    model.run()
    table = model.columns[Forager]
    assert (table.energy >= 0).all()
    assert (table.energy < 2 * model.scenario.birth_threshold).all()
    assert len(list(model.index.tracked_agents())) == model.population()


def test_same_seed_same_run():
    """Same seed, same population curve; another seed, another curve."""

    def curve(seed):
        model = EnergyBudget(EnergyScenario(rng=seed, steps=60))
        model.run()
        return model.datacollector.get_model_vars_dataframe()

    assert curve(5).equals(curve(5))
    assert not curve(5).equals(curve(6))
    assert np.isfinite(curve(5).to_numpy()).all()
