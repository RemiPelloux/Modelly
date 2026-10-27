"""Foragers on a nutrient field: the field's mass balance and the energy balance."""

import numpy as np
import pytest

from modelly.zoo.nutrient_foragers.model import (
    Forager,
    NutrientForagers,
    NutrientScenario,
)

BURN_IN = 150
# The population fluctuates by about 2 % of K from step to step; averaging 250 correlated
# steps leaves well under 1 %. The deficit of starving foragers (at most one cost each)
# lifts the mean about 1 % above K. 3 % covers both with room to spare.
RELATIVE_TOLERANCE = 0.03
# With the starvation deficit counted only the fluctuation is left.
BALANCED_TOLERANCE = 0.01
# Round-off on sums of a few hundred thousand terms of order one.
ROUND_OFF = 1e-10


def run(seed, **changes):
    """A finished run and its model-variable frame."""
    model = NutrientForagers(NutrientScenario(rng=seed, **changes))
    model.run()
    return model, model.datacollector.get_model_vars_dataframe()


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_population_settles_at_the_carrying_capacity(seed):
    """Without decay, the mean population is within 3 % of ``efficiency * supply / cost``."""
    model, frame = run(seed)
    assert model.carrying_capacity() == pytest.approx(0.5 * 40.0 * 20)
    mean = frame["foragers"].iloc[BURN_IN:].mean()
    assert mean == pytest.approx(model.carrying_capacity(), rel=RELATIVE_TOLERANCE)


@pytest.mark.parametrize("seed", [1, 2])
@pytest.mark.parametrize("decay", [0.0, 0.05])
def test_energy_balance_with_decay(seed, decay):
    """``cost * N = efficiency * (supply - decayed) + deficit`` per step, within 1 %."""
    model, frame = run(seed, decay=decay)
    s = model.scenario
    lost = np.diff(frame["decayed"].to_numpy())[BURN_IN:].mean()
    deficit = model.deficit / s.steps
    expected = (s.efficiency * (model.supply.sum() - lost) + deficit) / s.cost
    mean = frame["foragers"].iloc[BURN_IN:].mean()
    assert mean == pytest.approx(expected, rel=BALANCED_TOLERANCE)
    if decay:
        assert mean < 0.95 * model.carrying_capacity()


@pytest.mark.parametrize("decay", [0.0, 0.05])
def test_nutrient_budget_closes_to_round_off(decay):
    """Nutrient on the grid = supplied - eaten - decayed, exactly; closed walls leak nothing."""
    model, _ = run(4, decay=decay, steps=200)
    field = model.field
    supplied = model.supply.sum() * model.scenario.steps
    assert field.outflow == 0.0
    assert field.added == pytest.approx(supplied - model.eaten, rel=ROUND_OFF)
    assert field.total() == pytest.approx(field.added - field.decayed, rel=ROUND_OFF)
    assert (field.values >= 0).all()


def test_density_falls_away_from_the_river():
    """More foragers near the western supply than in the eastern half."""
    model, _ = run(5)
    density = model.density_by_column()
    assert density[:4].mean() > 10 * density[10:].mean()
    assert model.grid._cells[(0, 0)].nutrient == model.field.values[0, 0]


def test_no_supply_means_extinction():
    """Without nutrient every forager starves once its initial energy is spent."""
    model, _ = run(1, supply=0.0, steps=20)
    assert model.population() == 0
    model.step()  # an empty population still steps
    assert model.population() == 0
    assert model.density_by_column().sum() == 0


def test_field_runs_after_the_foragers_on_stable_sub_steps():
    """Foragers first, then the field, on sub-steps of half the explicit limit ``1 / (4 D)``."""
    model = NutrientForagers(NutrientScenario(rng=1, diffusion=2.0))
    assert model.coupling.order == ["Phase 'forage'", "Field 'nutrient'"]
    assert model.field.dt == pytest.approx(0.5 / (4 * 2.0))


def test_checkpoint_resumes_bit_for_bit(tmp_path):
    """Save at step 30, load, run 30 more: the same field and population as 60 straight."""
    straight, frame = run(6, steps=60)
    model = NutrientForagers(NutrientScenario(rng=6))
    model.run(30)
    model.save(tmp_path / "foragers.ckpt")
    resumed = NutrientForagers.load(tmp_path / "foragers.ckpt")
    resumed.run(30)
    assert np.array_equal(resumed.field.values, straight.field.values)
    assert np.array_equal(
        resumed.columns[Forager].energy, straight.columns[Forager].energy
    )
    assert resumed.datacollector.get_model_vars_dataframe().equals(frame)


def test_same_seed_same_run():
    """Same seed, same population curve; another seed, another curve."""
    assert run(7, steps=60)[1].equals(run(7, steps=60)[1])
    assert not run(7, steps=60)[1].equals(run(8, steps=60)[1])
