"""Axelrod culture model: monoculture for few traits, many regions for many."""

import numpy as np
import pytest

from modelly.zoo.axelrod.model import Axelrod, AxelrodScenario, interact

SEEDS = (1, 2, 3, 4, 5)
SITES = 100


def frozen(traits, seed):
    """The 10 x 10, five-feature model run until no bond is active."""
    model = Axelrod(AxelrodScenario(rng=seed, traits=traits))
    model.run()
    assert not model.running
    return model


def test_few_traits_end_in_monoculture():
    """With two traits per feature almost every pair overlaps: one culture wins."""
    regions = [frozen(2, seed).n_regions() for seed in SEEDS]
    assert sum(r == 1 for r in regions) >= len(SEEDS) - 1


def test_many_traits_leave_many_regions():
    """With thirty traits most neighbours share nothing and the map freezes fragmented.

    Axelrod's 10 x 10 runs with five features give tens of regions for large trait
    counts; a quarter of the sites is a safe floor.
    """
    regions = [frozen(30, seed).n_regions() for seed in SEEDS]
    assert min(regions) > SITES // 4


def test_regions_grow_with_traits():
    """Mean number of regions over the seeds is non-decreasing in the trait count."""
    means = [np.mean([frozen(q, s).n_regions() for s in SEEDS]) for q in (2, 15, 60)]
    assert means[0] < means[1] < means[2]


def test_frozen_map_has_only_identical_or_disjoint_neighbours():
    """The absorbing state: every bond has overlap 0 or F."""
    model = frozen(10, 1)
    overlap = model.overlaps()
    assert np.all((overlap == 0) | (overlap == model.scenario.features))


def test_interaction_rules():
    """No copy with nothing or everything in common; a copy makes the pair closer."""
    site, partner = [1, 2, 3], [4, 5, 6]
    interact(site, partner, 0.0, 0.0)
    assert site == [1, 2, 3]
    site, partner = [1, 2, 3], [1, 5, 6]
    # Accepted (overlap 1/3 > 0.0): the first differing feature is copied.
    interact(site, partner, 0.0, 0.0)
    assert site == [1, 5, 3]
    site = [1, 2, 3]
    interact(site, partner, 0.9, 0.0)  # 0.9 > 1/3: no interaction
    assert site == [1, 2, 3]


@pytest.mark.parametrize("traits", [3, 20])
def test_same_seed_same_run(traits):
    """Same seed, same culture map."""
    a = frozen(traits, 9).culture
    assert np.array_equal(a, frozen(traits, 9).culture)
    assert not np.array_equal(a, frozen(traits, 10).culture)
