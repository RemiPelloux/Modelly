"""Combinatorial optimisation by simulated annealing: whole households fit the totals."""

import numpy as np
import pandas as pd

from modelly.population import Annealing, anneal, total_absolute_error

# A synthetic sample of household records (no real microdata): members per age band.
SAMPLE = pd.DataFrame(
    {
        "children": [0, 0, 2, 1, 3, 0, 0, 1],
        "adults": [1, 2, 2, 1, 2, 0, 1, 2],
        "seniors": [0, 0, 0, 0, 0, 2, 1, 1],
    }
)
SIZE = 300


def targets_of(selection):
    """The totals of a selection of records: a target the sample can meet exactly."""
    return SAMPLE.iloc[selection].sum().astype(float).to_dict()


def test_anneal_recovers_reachable_totals():
    """Totals drawn from the sample itself are met exactly, or almost."""
    truth = np.random.default_rng(10).integers(len(SAMPLE), size=SIZE)
    targets = targets_of(truth)
    chosen = anneal(SAMPLE, targets, Annealing(SIZE), np.random.default_rng(11))
    assert chosen.shape == (SIZE,)
    start = np.random.default_rng(11).integers(len(SAMPLE), size=SIZE)
    assert total_absolute_error(SAMPLE, start, targets) > 20
    assert total_absolute_error(SAMPLE, chosen, targets) <= 2


def test_anneal_is_seeded_and_never_worse_than_its_start():
    """Same seed, same records; the fit is at least as good as the random start."""
    targets = {"children": 250.0, "adults": 400.0, "seniors": 90.0}
    settings = Annealing(SIZE, iterations=2_000)
    first = anneal(SAMPLE, targets, settings, np.random.default_rng(12))
    again = anneal(SAMPLE, targets, settings, np.random.default_rng(12))
    assert np.array_equal(first, again)
    start = np.random.default_rng(12).integers(len(SAMPLE), size=SIZE)
    assert total_absolute_error(SAMPLE, first, targets) <= total_absolute_error(
        SAMPLE, start, targets
    )
