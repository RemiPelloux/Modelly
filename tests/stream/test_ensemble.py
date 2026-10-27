"""Tests for ensembles and quantile bands (modelly.stream.ensemble, modelly.stream.bands)."""

import numpy as np
import pytest
from stream_support import (
    ENSEMBLE_SEED,
    PRIOR_HIGH,
    PRIOR_LOW,
    Town,
    TownScenario,
    cases,
    ensemble,
)

from modelly.stream import Ensemble, ObservationOperator
from modelly.stream.bands import _forecast_times, _normalised, weighted_quantiles
from modelly.stream.ensemble import RESAMPLE_DOMAIN

SEED = 5


def test_replicates_get_the_seeds_spawn_replications_gives():
    """Replicate i has the seed of spawn_replications(n)[i]; the scenario is untouched."""
    scenario = TownScenario(rng=SEED)
    first = Ensemble(Town, scenario, 3)
    second = Ensemble(Town, scenario, 3)
    spawned = TownScenario(rng=SEED).spawn_replications(3)
    for a, b, child in zip(first, second, spawned):
        assert a.scenario.seed_sequence.spawn_key == child.seed_sequence.spawn_key
        assert a.random.getstate() == b.random.getstate()
        assert a.scenario.replication_id == child.replication_id
    assert scenario.seed_sequence.n_children_spawned == 0


def test_prior_draws_differ_by_replicate_and_repeat_by_seed():
    """Each replicate draws its own value, the same ones for the same seed."""
    betas = [m.beta for m in ensemble()]
    assert len(set(betas)) == len(betas)
    assert all(PRIOR_LOW <= b <= PRIOR_HIGH for b in betas)
    assert betas == [m.beta for m in ensemble()]
    assert betas != [m.beta for m in ensemble(seed=ENSEMBLE_SEED + 1)]


def test_advance_runs_every_replicate_in_lock_step():
    """All replicates reach the time; the same time again is a no-op, the past an error."""
    members = ensemble(n=3)
    members.advance(4)
    assert [m.time for m in members] == [4.0, 4.0, 4.0]
    assert members.time == 4.0
    members.advance(4)
    with pytest.raises(ValueError, match="cannot advance"):
        members.advance(3)


def test_too_small_an_ensemble_is_refused():
    """An ensemble has at least two replicates."""
    with pytest.raises(ValueError, match="at least 2"):
        Ensemble(Town, TownScenario(rng=SEED), 1)


def test_resample_keeps_the_first_slot_and_copies_the_others():
    """The first slot of a replicate is the model itself, the others reseeded copies."""
    members = ensemble(n=3)
    members.advance(3)
    originals = list(members)
    members.resample([2, 2, 0], lambda slot: members.seed(RESAMPLE_DOMAIN, 0, slot))
    assert members[0] is originals[2] and members[2] is originals[0]
    copy = members[1]
    assert copy is not originals[2]
    assert copy.prevalence == originals[2].prevalence
    assert copy.random.getstate() != originals[2].random.getstate()
    members.advance(10)
    assert len(members) == 3


def test_resample_needs_one_index_per_slot():
    """The index list has the ensemble's length."""
    members = ensemble(n=3)
    with pytest.raises(ValueError, match="3 indices"):
        members.resample([0, 1], lambda slot: None)


def test_values_and_band_read_every_replicate():
    """``values`` stacks readings; the band has the mean and quantile columns."""
    members = ensemble(n=4)
    members.advance(5)
    values = members.values(cases())
    assert values.shape == (4, 1)
    band = members.band(cases(), quantiles=(0.25, 0.75))
    assert list(band.columns) == ["time", "quantity", "mean", "q0.25", "q0.75"]
    assert band.loc[0, "mean"] == pytest.approx(values.mean())
    assert band.loc[0, "time"] == 5.0


def test_forecast_runs_copies_and_leaves_the_ensemble():
    """The forecast reaches ``until``; the ensemble stays at its time."""
    members = ensemble(n=3)
    members.advance(2)
    operator = ObservationOperator(
        cases=lambda m: m.new_cases, infected=lambda m: m.prevalence
    )
    ahead = members.forecast(operator, 4)
    assert ahead["time"].tolist() == [2.0, 2.0, 3.0, 3.0, 4.0, 4.0]
    assert ahead["quantity"].tolist()[:2] == ["cases", "infected"]
    assert members.time == 2.0
    members.advance(4)
    final = members.band(operator)
    np.testing.assert_allclose(
        final["mean"].to_numpy(), ahead[ahead["time"] == 4.0]["mean"].to_numpy()
    )


def test_equal_weight_quantiles_are_hazen():
    """With equal weights the quantiles are numpy's Hazen definition."""
    values = np.random.default_rng(1).normal(size=37)
    levels = [0.05, 0.3, 0.5, 0.9]
    np.testing.assert_allclose(
        weighted_quantiles(values, None, levels),
        np.quantile(values, levels, method="hazen"),
    )


def test_weights_shift_the_quantiles():
    """All weight on one value puts every quantile there."""
    assert weighted_quantiles([1, 2, 3], [0, 1, 0], [0.1, 0.9]).tolist() == [2, 2]


def test_invalid_weights_are_refused():
    """Weights are n non-negative numbers, not all zero."""
    for bad in ([1, -1], [0, 0], [1, 2, 3]):
        with pytest.raises(ValueError, match="weights"):
            _normalised(bad, 2)


def test_forecast_times_end_exactly_at_until():
    """Steps of ``every`` from the start, with ``until`` itself last."""
    assert _forecast_times(0, 2.5, 1.0) == [0, 1.0, 2.0, 2.5]
    assert _forecast_times(3, 3, 1.0) == [3]
    with pytest.raises(ValueError, match="positive"):
        _forecast_times(0, 1, 0)
    with pytest.raises(ValueError, match="back"):
        _forecast_times(2, 1, 1.0)
