"""Tests for the ABC-SMC perturbation kernels."""

import math

import numpy as np
import pytest

from modelly.calibrate import Prior
from modelly.calibrate.kernels import COVARIANCE_SCALE, Kernel, joint_logprior

PRIORS = {"a": Prior.uniform(0.0, 1.0), "k": Prior.choice([1, 2, 3])}
POPULATION = {"a": [0.2, 0.4, 0.6, 0.8], "k": [1, 1, 2, 3]}
WEIGHTS = np.full(4, 0.25)


def test_covariance_is_twice_the_weighted_one():
    """The continuous kernel's covariance is twice the population's."""
    kernel = Kernel.fit(PRIORS, POPULATION, WEIGHTS)
    variance = np.var(POPULATION["a"])
    assert kernel.covariance[0, 0] == pytest.approx(COVARIANCE_SCALE * variance)
    assert kernel.continuous == ["a"] and kernel.discrete == ["k"]


def test_proposals_are_seeded_and_inside_the_prior():
    """The same stream gives the same proposals, all with a finite prior density."""
    kernel = Kernel.fit(PRIORS, POPULATION, WEIGHTS)
    first = kernel.propose(np.random.default_rng(3), 50)
    second = kernel.propose(np.random.default_rng(3), 50)
    assert first == second
    assert np.isfinite(joint_logprior(PRIORS, first)).all()
    assert set(first["k"]) <= {1, 2, 3}


def test_discrete_kernel_is_a_distribution():
    """From any value, the moves to every value sum to probability one."""
    kernel = Kernel.fit(PRIORS, POPULATION, WEIGHTS)
    density = kernel._choice_logpdf("k", [1, 2, 3], [1])
    assert np.exp(density).sum() == pytest.approx(1.0)
    single = Kernel.fit({"k": Prior.choice([7])}, {"k": [7, 7]}, np.full(2, 0.5))
    assert single.logpdf({"k": [7]}).tolist() == [[0.0, 0.0]]
    assert single.propose(np.random.default_rng(0), 3) == {"k": [7, 7, 7]}


def test_importance_weights_favour_unlikely_proposals():
    """Prior over mixture density: a point far from the population weighs more."""
    priors = {"a": Prior.uniform(0.0, 1.0)}
    kernel = Kernel.fit(priors, {"a": [0.5, 0.5, 0.55]}, np.full(3, 1 / 3))
    near, far = kernel.importance({"a": [0.5, 0.9]})
    assert far > near
    assert math.isfinite(near)


def test_kernel_logpdf_shape():
    """``logpdf`` is an array [new, population]."""
    kernel = Kernel.fit(PRIORS, POPULATION, WEIGHTS)
    assert kernel.logpdf({"a": [0.1, 0.2], "k": [1, 3]}).shape == (2, 4)


def test_weighted_proposals_follow_the_prior_up_to_its_bound():
    """Importance weights undo the proposal: weighted proposals are uniform, even at 0.

    The population crowds the lower bound, so many moves leave the support; a proposal
    that re-moved the same ancestor would over-weight the bins next to the bound.
    """
    priors = {"a": Prior.uniform(0.0, 1.0)}
    population = {"a": list(np.random.default_rng(1).beta(1, 8, size=100))}
    kernel = Kernel.fit(priors, population, np.full(100, 0.01))
    proposal = kernel.propose(np.random.default_rng(2), 40_000)
    weights = np.exp(kernel.importance(proposal))
    mass, _ = np.histogram(proposal["a"], bins=5, range=(0.0, 0.5), weights=weights)
    share = mass / mass.sum()
    assert share == pytest.approx(np.full(5, 0.2), rel=0.08)
