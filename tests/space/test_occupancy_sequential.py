"""Tests for the sequential fallback of claim, used once the vectorised rounds run out."""

import numpy as np
import pytest

from modelly.space.cells import occupancy as occupancy_module
from modelly.space.cells.occupancy import NO_MATCH, Occupancy, claim


def _check_matching(rows, claimants, matched):
    served = matched != NO_MATCH
    members = np.bincount(rows, minlength=claimants.max() + 1)
    wanted = np.bincount(claimants, minlength=members.shape[0])
    got = np.bincount(claimants[served], minlength=members.shape[0])
    assert (got == np.minimum(wanted, members)).all()
    assert len(set(matched[served].tolist())) == served.sum()
    assert (rows[matched[served]] == claimants[served]).all()


@pytest.mark.parametrize("rounds", [0, 1])
def test_claim_sequential_fallback_keeps_the_rule(monkeypatch, rounds):
    """With few or no vectorised rounds the remaining claimants are served one by one."""
    monkeypatch.setattr(occupancy_module, "MAX_VECTOR_ROUNDS", rounds)
    rows = np.repeat(np.arange(5), [4, 1, 0, 3, 6])
    claimants = np.repeat(np.arange(5), [6, 2, 3, 3, 1])
    occ = Occupancy(rows, n_cells=5)
    matched = claim(occ, claimants, np.random.default_rng(11))
    _check_matching(rows, claimants, matched)
    assert (matched[claimants == 2] == NO_MATCH).all()


def test_claim_sequential_is_deterministic_per_seed(monkeypatch):
    """Claim sequential is deterministic per seed."""
    monkeypatch.setattr(occupancy_module, "MAX_VECTOR_ROUNDS", 0)
    rows = np.zeros(6, dtype=int)
    claimants = np.zeros(4, dtype=int)
    occ = Occupancy(rows, n_cells=1)
    first = claim(occ, claimants, np.random.default_rng(5))
    second = claim(occ, claimants, np.random.default_rng(5))
    assert first.tolist() == second.tolist()


def test_claim_sequential_law_takes_members_uniformly(monkeypatch):
    """Each of 4 members is taken with probability 2/4 when 2 claimants pick."""
    monkeypatch.setattr(occupancy_module, "MAX_VECTOR_ROUNDS", 0)
    rng = np.random.default_rng(8)
    occ = Occupancy(np.zeros(4, dtype=int), n_cells=1)
    taken = np.zeros(4)
    trials = 2000
    for _ in range(trials):
        taken[claim(occ, np.zeros(2, dtype=int), rng)] += 1
    assert np.allclose(taken / trials, 0.5, atol=0.05)


def test_claim_sequential_skips_cells_that_ran_out(monkeypatch):
    """Claim sequential skips cells that ran out."""
    monkeypatch.setattr(occupancy_module, "MAX_VECTOR_ROUNDS", 0)
    occ = Occupancy(np.array([0]), n_cells=2)
    matched = claim(occ, np.array([0, 0, 0]), np.random.default_rng(1))
    assert sorted(matched.tolist()) == [NO_MATCH, NO_MATCH, 0]
