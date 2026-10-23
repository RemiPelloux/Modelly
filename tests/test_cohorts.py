"""CohortTable: counted populations with binomial thinning, splitting and merging."""

import numpy as np
import pytest

from modelly import CohortTable
from modelly.cohorts import from_counts

EGG, ADULT = 0, 3


def make(seed=1):
    """A table with three cohorts."""
    table = CohortTable(np.random.default_rng(seed), stage=np.int8, age=np.int16)
    table.add([100, 50, 0], stage=[EGG, ADULT, ADULT], age=[0, 4, 9])
    return table


def test_add_columns_totals_and_views():
    """Rows hold counts and state; views write through."""
    table = make()
    assert len(table) == 3 and table.total() == 150
    assert table.columns == ["count", "stage", "age"]
    assert table.totals_by("stage", minlength=4).tolist() == [100, 0, 0, 50]
    table["age"] += 1
    assert table["age"].tolist() == [1, 5, 10]
    assert table.total(table["stage"] == ADULT) == 50
    with pytest.raises(KeyError):
        table.add(1, colour=2)
    with pytest.raises(ValueError):
        table.add([1, 2], stage=[1, 2, 3])
    with pytest.raises(ValueError):
        CohortTable(np.random.default_rng(1), count=int)


def test_thin_is_binomial_per_row():
    """Survivors are Binomial(count, s): mean n*s, never more than n."""
    table = CohortTable(np.random.default_rng(3), stage=np.int8)
    table.add(np.full(2000, 1000))
    survivors = table.thin(0.9)
    assert (survivors <= 1000).all()
    assert abs(survivors.mean() - 900) < 1.5
    assert abs(survivors.var() - 1000 * 0.9 * 0.1) < 10
    table.thin(np.where(np.arange(2000) < 1000, 0.0, 1.0))
    assert table["count"][:1000].sum() == 0
    assert (table["count"][1000:] == survivors[1000:]).all()


def test_split_moves_individuals_without_changing_the_total():
    """Split conserves individuals and copies the state before the changes."""
    table = make()
    before = table.total()
    new = table.split(0.5, where=table["stage"] == EGG, stage=ADULT, age=0)
    assert table.total() == before
    assert table["stage"][new].tolist() == [ADULT]
    moved = int(table["count"][new][0])
    assert table["count"][0] == 100 - moved
    assert 20 < moved < 80


def test_draw_does_not_change_counts():
    """Drawing returns events and leaves the table alone."""
    table = make()
    events = table.draw(0.5)
    assert table["count"].tolist() == [100, 50, 0]
    assert events.shape == (3,) and events[2] == 0


def test_compact_and_merge_keep_one_row_per_state():
    """Compacting drops empties in order; merging sums identical states."""
    table = make()
    table.add([5, 7], stage=[ADULT, EGG], age=[4, 0])
    assert table.compact() == 1
    assert len(table) == 4
    assert table.merge() == 2
    rows = sorted(
        zip(table["stage"].tolist(), table["age"].tolist(), table["count"].tolist())
    )
    assert rows == [(EGG, 0, 107), (ADULT, 4, 55)]


def test_growth_and_dataframe():
    """The table grows past its initial capacity and exports a copy."""
    table = CohortTable(np.random.default_rng(1), stage=np.int8)
    for i in range(300):
        table.add(i, stage=i % 4)
    assert len(table) == 300 and table.total() == sum(range(300))
    frame = table.to_dataframe()
    frame.loc[0, "count"] = -1
    assert table["count"][0] == 0
    assert "300 cohorts" in repr(table)


def test_from_counts_builds_one_row_per_state():
    """from_counts maps state tuples to rows."""
    table = from_counts(
        np.random.default_rng(1),
        {(EGG, 0): 4, (ADULT, 2): 6},
        stage=np.int8,
        age=np.int16,
    )
    assert table["count"].tolist() == [4, 6]
    assert table["stage"].tolist() == [EGG, ADULT]
    assert from_counts(np.random.default_rng(1), {}, stage=np.int8).total() == 0
