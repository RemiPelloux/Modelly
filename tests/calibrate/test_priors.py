"""Tests for Prior: seeded sampling, densities, support, validation."""

import math

import numpy as np
import pytest

from modelly.calibrate import Prior

CONTINUOUS = [
    Prior.uniform(0.1, 0.5),
    Prior.log_uniform(1e-3, 1.0),
    Prior.normal(0.0, 2.0),
    Prior.log_normal(-2.0, 0.5),
    Prior.truncated_normal(0.3, 0.2, low=0.0, high=1.0),
]


@pytest.mark.parametrize("prior", CONTINUOUS, ids=lambda p: p.kind)
def test_sampling_is_seeded_and_in_support(prior):
    """The same generator state gives the same draws, all with finite density."""
    first = prior.sample(np.random.default_rng(5), 200)
    second = prior.sample(np.random.default_rng(5), 200)
    np.testing.assert_array_equal(first, second)
    assert np.isfinite(prior.logpdf(first)).all()
    low, high = prior.bounds()
    assert low < prior.median() < high


def test_uniform_density_and_support():
    """A uniform density is 1 / width inside and -inf outside."""
    prior = Prior.uniform(0.0, 4.0)
    assert prior.logpdf(1.0) == pytest.approx(-math.log(4.0))
    assert prior.logpdf(5.0) == -math.inf
    assert prior.bounds() == (0.0, 4.0)


def test_truncated_normal_stays_inside():
    """A truncated normal never draws outside its bounds."""
    prior = Prior.truncated_normal(0.0, 1.0, low=-0.5, high=0.5)
    draws = prior.sample(np.random.default_rng(1), 1000)
    assert draws.min() >= -0.5 and draws.max() <= 0.5
    assert prior.logpdf(0.6) == -math.inf


def test_unbounded_prior_bounds_cover_the_centre():
    """An unbounded prior is searched over its central quantiles."""
    low, high = Prior.normal(0.0, 1.0).bounds()
    assert low == pytest.approx(-3.09, abs=0.01) and high == pytest.approx(
        3.09, abs=0.01
    )


def test_choice_prior():
    """A choice draws its values with their probabilities and has a log probability."""
    prior = Prior.choice(["a", "b", "c"], probabilities=[0.5, 0.5, 0.0])
    draws = prior.sample(np.random.default_rng(2), 100)
    assert set(draws) <= {"a", "b"}
    assert prior.logpdf("a") == pytest.approx(math.log(0.5))
    assert prior.logpdf("c") == -math.inf
    assert prior.logpdf("z") == -math.inf
    assert list(prior.logpdf(np.array(["a", "c"], dtype=object))) == [
        pytest.approx(math.log(0.5)),
        -math.inf,
    ]
    assert prior.median() == "a"
    assert prior.discrete
    with pytest.raises(TypeError):
        prior.bounds()
    with pytest.raises(TypeError):
        prior.distribution()


@pytest.mark.parametrize(
    "build",
    [
        lambda: Prior.uniform(1.0, 1.0),
        lambda: Prior.log_uniform(0.0, 1.0),
        lambda: Prior.normal(0.0, 0.0),
        lambda: Prior.log_normal(0.0, -1.0),
        lambda: Prior.choice([]),
        lambda: Prior.choice(["a", "a"]),
        lambda: Prior.choice(["a", "b"], probabilities=[0.2, 0.2]),
        lambda: Prior.choice(["a", "b"], probabilities=[1.5, -0.5]),
        lambda: Prior("beta", {}),
    ],
)
def test_invalid_priors(build):
    """Impossible parameters are a ValueError."""
    with pytest.raises(ValueError):
        build()
