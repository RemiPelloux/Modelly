"""Tests for Occupancy and claim: grouping by cell row and the vectorised matching."""

import numpy as np

from modelly.space import NO_MATCH, Occupancy, claim


def test_occupancy_groups_table_indices_by_cell():
    """members() and counts() read the sorted order; random_member picks inside the cell."""
    rows = np.array([3, 0, 3, 2, 3, 0])
    occupancy = Occupancy(rows, n_cells=5)
    assert occupancy.counts().tolist() == [2, 0, 1, 3, 0]
    assert sorted(occupancy.members(3).tolist()) == [0, 2, 4]
    assert occupancy.members(1).tolist() == []
    rng = np.random.default_rng(1)
    picks = occupancy.random_member(np.array([3, 1, 0, 3]), rng)
    assert picks[1] == NO_MATCH
    assert all(rows[p] == c for p, c in zip(picks, [3, 1, 0, 3]) if p != NO_MATCH)


def test_claim_serves_min_of_claimants_and_members_with_distinct_matches():
    """Every cell ends with min(claimants, members) matches, all distinct."""
    rng = np.random.default_rng(2)
    rows = np.repeat(np.arange(6), [5, 1, 0, 3, 2, 4])
    claimants = np.repeat(np.arange(6), [2, 3, 2, 3, 2, 0])
    occupancy = Occupancy(rows, n_cells=6)
    matched = claim(occupancy, claimants, rng)
    served = matched != NO_MATCH
    assert np.bincount(claimants[served], minlength=6).tolist() == [2, 1, 0, 3, 2, 0]
    assert len(set(matched[served].tolist())) == served.sum()
    assert (rows[matched[served]] == claimants[served]).all()


def test_claim_has_the_sequential_law():
    """3 claimants, 5 members: each member is taken with probability 3/5, each claimant served."""
    rng = np.random.default_rng(3)
    rows = np.zeros(5, dtype=int)
    claimants = np.zeros(3, dtype=int)
    occupancy = Occupancy(rows, n_cells=1)
    trials = 4000
    taken = np.zeros(5)
    for _ in range(trials):
        matched = claim(occupancy, claimants, rng)
        assert (matched != NO_MATCH).all()
        taken[matched] += 1
    frequencies = taken / trials
    assert np.allclose(frequencies, 0.6, atol=0.03)


def test_claim_with_more_claimants_than_members_serves_a_uniform_subset():
    """5 claimants, 2 members: exactly two served, each claimant with probability 2/5."""
    rng = np.random.default_rng(4)
    occupancy = Occupancy(np.zeros(2, dtype=int), n_cells=1)
    served = np.zeros(5)
    for _ in range(4000):
        matched = claim(occupancy, np.zeros(5, dtype=int), rng)
        assert (matched != NO_MATCH).sum() == 2
        served += matched != NO_MATCH
    assert np.allclose(served / 4000, 0.4, atol=0.03)
