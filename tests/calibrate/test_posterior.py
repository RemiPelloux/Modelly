"""Tests for Posterior: weighted summaries, HDI, export, prediction and plots."""

import numpy as np
import pytest

from modelly.calibrate.posterior import hdi, weighted_quantile
from tests.calibrate.shared import STEPS, sir_smc

pytest.importorskip("pyarrow")


def test_weighted_quantile_and_hdi():
    """Quantiles follow the weights; the HDI is the shortest interval of the mass."""
    values = np.array([0.0, 1.0, 2.0, 3.0, 100.0])
    weights = np.array([0.1, 0.2, 0.4, 0.2, 0.1])
    assert weighted_quantile(values, weights, 0.5) == 2.0
    assert weighted_quantile(values, np.ones(5), 0.0) == 0.0
    assert hdi(values, weights, 0.8) == (1.0, 3.0)
    assert hdi(values, weights, 1.0) == (0.0, 100.0)


@pytest.fixture(scope="module")
def posterior():
    """A small SIR posterior."""
    return sir_smc(particles=20).run(generations=2)


def test_summary_and_dataframe(posterior):
    """One summary row per parameter; one DataFrame row per sample."""
    summary = posterior.summary()
    assert list(summary.columns) == ["mean", "median", "sd", "hdi_low", "hdi_high"]
    assert list(summary.index) == ["beta", "gamma"]
    assert (summary["hdi_low"] <= summary["median"]).all()
    assert (summary["median"] <= summary["hdi_high"]).all()
    frame = posterior.to_dataframe()
    assert list(frame.columns) == ["beta", "gamma", "weight", "distance"]
    assert len(frame) == len(posterior) == 20
    assert set(posterior.best) == {"beta", "gamma"}
    assert "abc-smc" in repr(posterior)


def test_predict_is_seeded(posterior):
    """Posterior predictive runs: one row per draw, replicate and step, the same twice."""
    first = posterior.predict(draws=3)
    assert len(first) == 3 * (STEPS + 1)
    assert {"draw", "sample", "replicate", "step", "infected"} <= set(first.columns)
    np.testing.assert_array_equal(
        first["infected"], posterior.predict(draws=3)["infected"]
    )


def test_plot(posterior):
    """The figure has the pairs grid and one fit panel per target."""
    pytest.importorskip("matplotlib")
    figure = posterior.plot()
    assert len(figure.axes) == 2 * 2 + 1
    assert figure.axes[-1].get_title() == "infected"
