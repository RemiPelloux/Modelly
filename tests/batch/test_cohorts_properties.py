"""Property-based tests for cohort tables: thin, split and merge conserve individuals."""

import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from modelly.batch.cohorts import CohortTable

MAX_COHORTS = 20
MAX_COUNT = 10_000
MAX_STAGE = 4

cohorts = st.lists(
    st.tuples(st.integers(0, MAX_COUNT), st.integers(0, MAX_STAGE)),
    max_size=MAX_COHORTS,
)
seeds = st.integers(0, 2**32 - 1)
probabilities = st.floats(0.0, 1.0)


def _table(seed, rows):
    table = CohortTable(np.random.default_rng(seed), stage=np.int8)
    if rows:
        counts, stages = zip(*rows)
        table.add(list(counts), stage=np.array(stages))
    return table


@given(seed=seeds, rows=cohorts, survival=probabilities)
def test_thin_never_creates_individuals(seed, rows, survival):
    """Every count after thinning is between zero and the count before."""
    table = _table(seed, rows)
    before = table["count"].copy()
    after = table.thin(survival)
    assert ((after >= 0) & (after <= before)).all()
    if survival == 1.0:
        assert np.array_equal(after, before)


@given(seed=seeds, rows=cohorts, p=probabilities, stage=st.integers(0, MAX_STAGE))
def test_split_conserves_the_total(seed, rows, p, stage):
    """Moving individuals to new rows keeps the total and the per-row source counts."""
    table = _table(seed, rows)
    total = table.total()
    sources = len(table)
    new_rows = table.split(p, stage=stage)
    assert table.total() == total
    assert len(new_rows) == sources
    assert (table["stage"][new_rows] == stage).all()


@given(seed=seeds, rows=cohorts)
def test_merge_conserves_counts_per_state(seed, rows):
    """Merging leaves one row per state, with the same individuals in each state."""
    table = _table(seed, rows)
    by_stage = table.totals_by("stage", minlength=MAX_STAGE + 1)
    table.merge()
    assert np.array_equal(table.totals_by("stage", minlength=MAX_STAGE + 1), by_stage)
    stages = table["stage"].tolist()
    assert len(stages) == len(set(stages))
    assert (table["count"] > 0).all()
