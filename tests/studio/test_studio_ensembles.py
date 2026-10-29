"""Ensembles of the session's model, and the particle and Kalman filters run from Studio."""

import numpy as np
import pandas as pd
import pytest

from modelly.scenarios import Scenario
from modelly.stream.particle import effective_sample_size
from modelly.stream.sources import Observation
from modelly.studio.assimilation import (
    KALMAN,
    FilterSettings,
    adjustable,
    assimilate,
    observation_frame,
    read_observations,
)
from modelly.studio.ensembles import (
    NoReportersError,
    ensemble_of,
    factory_and_scenario,
    reporter_operator,
    session_bands,
)
from tests.studio.models import Growth
from tests.studio.test_studio_recording import WOLF_SHEEP, session_of

GROWTH = "tests.studio.models:Growth"
BAND_COLUMNS = ["time", "quantity", "mean", "q0.05", "q0.5", "q0.95"]
TRUE_RATE = 0.2
OBSERVED_STEPS = range(2, 21, 2)


def truth_observations(rate=TRUE_RATE, seed=123) -> list[Observation]:
    """The count of one Growth run at ``rate``, every other step."""
    model = Growth(rate=rate, rng=seed)
    found = []
    for step in range(1, max(OBSERVED_STEPS) + 1):
        model.step()
        if step in OBSERVED_STEPS:
            found.append(Observation(float(step), {"count": model.count}))
    return found


def test_bands_across_replicates():
    """One row per step and reporter, the band columns, the same for the same seed."""
    session = session_of(WOLF_SHEEP)
    bands = session_bands(session, replicates=4, steps=5)
    assert list(bands.columns) == BAND_COLUMNS
    assert len(bands) == 6 * 3  # steps 0..5, three reporters
    assert set(bands["quantity"]) == {"Wolves", "Sheep", "Grass"}
    assert (bands["q0.05"] <= bands["q0.95"]).all()
    pd.testing.assert_frame_equal(bands, session_bands(session, replicates=4, steps=5))


def test_replicates_follow_the_panel():
    """Replicate seeds are spawned from the panel's seed; values reach every replicate."""
    session = session_of(WOLF_SHEEP)
    session.values["initial_sheep"] = 30
    session.seed = 9
    ensemble = ensemble_of(session, 3)
    assert all(m.scenario.initial_sheep == 30 for m in ensemble)
    expected = Scenario(rng=9).spawn_replications(3)
    spawned = [m.scenario.seed_sequence.spawn_key for m in ensemble]
    assert spawned == [s.seed_sequence.spawn_key for s in expected]


def test_a_model_without_a_scenario_class():
    """Constructor keywords go to the factory; the seed comes from a plain Scenario."""
    factory, scenario = factory_and_scenario(Growth, {"rate": 0.3}, 5)
    assert type(scenario) is Scenario
    model = factory(scenario=scenario)
    assert model.rate == 0.3
    with pytest.raises(NoReportersError, match="DataCollector"):
        reporter_operator(session_of("tests.studio.models:Silent").model)


def test_the_particle_filter_dashboard_data():
    """Weights sum to one, their ESS is the filter's, bands at every observation."""
    session = session_of(GROWTH)
    observations = truth_observations()
    result = assimilate(session, observations, FilterSettings(replicates=8, sd=2.0))
    assert result.weights.shape == (len(observations), 8)
    np.testing.assert_allclose(result.weights.sum(axis=1), 1.0)
    ess = [effective_sample_size(row) for row in result.weights.to_numpy()]
    np.testing.assert_allclose(ess, result.history["ess"])
    assert sorted(set(result.bands["time"])) == [o.time for o in observations]
    assert len(result.observations) == len(observations)


def test_the_kalman_filter_moves_the_parameter():
    """Starting at half the true rate, the ensemble mean moves towards it."""
    session = session_of(GROWTH)
    assert adjustable(session) == ["count", "rate"]
    settings = FilterSettings(
        method=KALMAN, replicates=20, sd=1.0, parameters=("rate",), spread=0.9
    )
    result = assimilate(session, truth_observations(), settings)
    history = result.history
    assert list(history.columns) == ["time", "rate", "rate_sd"]
    first, last = history["rate"].iloc[0], history["rate"].iloc[-1]
    assert abs(last - TRUE_RATE) < abs(first - TRUE_RATE)
    assert result.weights.empty


def test_assimilation_errors():
    """No observations, an unknown method, or a Kalman filter with no parameter."""
    session = session_of(GROWTH)
    with pytest.raises(ValueError, match="no observations"):
        assimilate(session, [])
    with pytest.raises(ValueError, match="method must be"):
        assimilate(session, truth_observations(), FilterSettings(method="magic"))
    with pytest.raises(ValueError, match="at least one parameter"):
        assimilate(session, truth_observations(), FilterSettings(method=KALMAN))


def test_observations_from_a_csv_file(tmp_path):
    """A CSV with a time column reads into observations, then long-format rows."""
    path = tmp_path / "observed.csv"
    path.write_text("time,count,other\n2,11.5,\n4,13.0,1\n", encoding="utf-8")
    observations = read_observations(path)
    assert [o.time for o in observations] == [2.0, 4.0]
    frame = observation_frame(observations)
    assert list(frame.columns) == ["time", "quantity", "value"]
    assert len(frame) == 3  # the empty field is dropped
