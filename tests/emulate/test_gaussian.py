"""Tests for the Gaussian-process emulator and the process's new pieces."""

import numpy as np
import pytest

from modelly.calibrate.gp import GaussianProcess, _negative_log_likelihood
from modelly.emulate import GaussianEmulator
from modelly.experiments import ScenarioSpace
from modelly.sensitivity import sobol


def smooth(units):
    """Two outputs of very different scale over the unit square."""
    first = np.sin(5 * units[:, 0]) + units[:, 1] ** 2
    return np.column_stack([first, 100 * units[:, 0] * units[:, 1]])


@pytest.fixture(name="data")
def fixture_data():
    """Twenty-five random points of the unit square and their outputs."""
    units = np.random.default_rng(3).random((25, 2))
    return units, smooth(units)


def test_restarts_find_a_likelier_fit(data):
    """Restarts never end at a less likely fit than the single start."""
    units, values = data
    standard = (values[:, 0] - values[:, 0].mean()) / values[:, 0].std()

    def likelihood(process):
        theta = np.append(np.log(process.lengths), np.log(process.noise))
        return _negative_log_likelihood(theta, units, standard)

    single = GaussianProcess.fit(units, values[:, 0])
    several = GaussianProcess.fit(units, values[:, 0], restarts=True)
    assert likelihood(several) <= likelihood(single) + 1e-9


def test_condition_keeps_the_mean_and_shrinks_the_variance(data):
    """Conditioning on predicted values leaves the mean and lowers the sd there."""
    units, values = data
    process = GaussianProcess.fit(units, values[:, 0], restarts=True)
    new = np.array([[0.5, 0.5], [0.05, 0.95]])
    conditioned = process.condition(new)
    np.testing.assert_allclose(conditioned.predict(new)[0], process.predict(new)[0])
    assert (conditioned.predict(new)[1] < process.predict(new)[1]).all()
    np.testing.assert_allclose(
        np.sqrt(np.diag(process.covariance(new, new))), process.predict(new)[1]
    )


def test_emulator_predicts_every_output(data):
    """One process per output; accurate on held-out points; select keeps one."""
    units, values = data
    emulator = GaussianEmulator.fit(units, values, ["wave", "product"])
    test = np.random.default_rng(4).random((200, 2))
    scores = emulator.score(test, smooth(test))
    assert set(scores) == {"wave", "product"}
    assert max(scores.values()) < 0.05
    mean, sd = emulator.predict(test)
    assert mean.shape == sd.shape == (200, 2)
    product = emulator.select("product")
    np.testing.assert_allclose(product.predict_unit(test), mean[:, 1])
    assert emulator.covariance(test[:3], test[:4]).shape == (2, 3, 4)
    assert emulator.noise_variance.shape == (2,)
    with pytest.raises(KeyError):
        emulator.select("nope")
    with pytest.raises(ValueError):
        emulator.predict_unit(test)


def test_emulator_stands_in_for_the_model_in_sobol():
    """A one-output emulator with its space is a valid input of sobol."""
    space = ScenarioSpace(a=(0.0, 1.0), b=(0.0, 1.0))
    units = np.random.default_rng(5).random((40, 2))
    emulator = GaussianEmulator.fit(
        units, 3 * units[:, 0] + 0.1 * units[:, 1], space=space
    )
    result = sobol(emulator, space, samples=512, seed=1)
    assert result.table.loc["a", "S1"] > result.table.loc["b", "S1"]


def test_emulator_from_an_experiment(tmp_path):
    """from_results averages replicates per point and inverts the space's map."""
    pytest.importorskip("pyarrow")
    pytest.importorskip("duckdb")
    from modelly.experiments import Experiment, designs  # noqa: PLC0415
    from tests.sensitivity.models import Response  # noqa: PLC0415

    space = ScenarioSpace(a=(0.0, 1.0), b=(0.0, 1.0), c=0.5, d=0.5)
    experiment = Experiment(
        model=Response, space=space, design=designs.latin_hypercube(30),
        replicates=2, steps=1, outputs=["value"], store=tmp_path / "runs", seed=2,
    )  # fmt: skip
    experiment.run(executor="serial")
    emulator = GaussianEmulator.from_results(experiment.results(), space, ["value"])
    assert emulator.space is space
    assert len(emulator.processes) == 1
    middle = emulator.predict([[0.5, 0.5]])[0][0, 0]
    assert middle == pytest.approx(10 * 0.5 + 4 * 0.25 + 0.5, abs=0.2)
