"""DeviceTable and DeviceCohortTable: column phases and cohorts on a backend."""

import numpy as np
import pytest

from modelly import Agent, CohortTable, Column, Model
from modelly.gpu import DeviceCohortTable, DeviceTable, PhiloxStream

SEED = 5
EGG, LARVA, ADULT = 0, 1, 3
SHORT_SEASON = 12


class Walker(Agent):
    """An agent with two columns."""

    energy = Column(float, default=1.0)
    alive = Column(np.int8, default=1)


def walkers(n=50):
    """A model with ``n`` walkers whose energy is their index."""
    model = Model(rng=1)
    Walker.create_agents(model, n)
    table = model.columns[Walker]
    table.energy = np.arange(n, dtype=float)
    return model, table


def test_device_table_reads_and_replaces_columns():
    """Columns are arrays; assignment replaces them, cast to their dtype."""
    _, host = walkers()
    table = DeviceTable.from_columns(host, PhiloxStream(SEED))
    assert len(table) == 50 and "energy" in table and table.columns[0] == "unique_id"
    table.energy = table.energy * 2
    table.alive = 0
    table.set_where("energy", table.energy > 90, -1.0)
    assert table["alive"].dtype == np.int8 and int(table.alive.sum()) == 0
    assert (table.to_numpy("energy") == -1.0).sum() == 4
    with pytest.raises(ValueError):
        table.energy = np.zeros(3)
    with pytest.raises(AttributeError):
        _ = table.colour


def test_device_table_writes_back_to_the_agents():
    """write_to copies the device columns into the agents' rows."""
    model, host = walkers()
    table = DeviceTable.from_columns(host, PhiloxStream(SEED), ["energy"])
    table.energy = table.energy + 0.5
    table.write_to(host)
    assert model.agents[3].energy == 3.5
    frame = DeviceTable(
        PhiloxStream(SEED), unique_id=np.arange(3), x=np.ones(3)
    ).to_dataframe()
    assert frame.index.name == "unique_id"
    with pytest.raises(ValueError):
        DeviceTable(PhiloxStream(SEED), energy=np.zeros(5)).write_to(host)


def test_device_table_rejects_ragged_columns():
    """Columns of different lengths are refused."""
    with pytest.raises(ValueError):
        DeviceTable(PhiloxStream(SEED), a=np.zeros(2), b=np.zeros(3))


def test_device_table_draw_and_thin():
    """Draw is one Bernoulli per row; thin replaces counts by binomials."""
    table = DeviceTable(PhiloxStream(SEED), count=np.full(10_000, 20))
    assert abs(table.draw(0.25).mean() - 0.25) < 0.02
    thinned = table.thin("count", 0.5)
    assert abs(thinned.mean() - 10) < 0.2 and "10000 rows" in repr(table)


def cohorts(stream):
    """A device table with three cohorts."""
    table = DeviceCohortTable(stream, stage=np.int8, age=np.int16)
    table.add([100, 50, 0], stage=[EGG, ADULT, ADULT], age=[0, 4, 9])
    return table


def test_device_cohorts_mirror_the_host_api():
    """Totals, per-stage totals, functional updates and compaction."""
    table = cohorts(PhiloxStream(SEED))
    assert len(table) == 3 and table.total() == 150 and table.columns[0] == "count"
    assert table.totals_by("stage", minlength=4).tolist() == [100, 0, 0, 50]
    table["age"] = table["age"] + 1
    table.set_where("stage", table["stage"] == EGG, LARVA)
    assert (
        table["age"].tolist() == [1, 5, 10]
        and table.total(table["stage"] == LARVA) == 100
    )
    assert table.compact() == 1 and len(table) == 2
    with pytest.raises(KeyError):
        table.add(1, colour=2)
    with pytest.raises(ValueError):
        DeviceCohortTable(PhiloxStream(SEED), count=int)


def test_device_cohorts_thin_split_draw_merge():
    """The binomial operations keep the totals they must, and merge sums equal states."""
    table = cohorts(PhiloxStream(SEED))
    table.thin(np.array([0.5, 1.0, 1.0]))
    assert table["count"][1] == 50 and 0 <= table["count"][0] <= 100
    before = table.total()
    rows = table.split(0.5, where=table["stage"] == ADULT, age=0)
    assert table.total() == before and table["age"][rows].tolist() == [0, 0]
    assert table.draw(1.0, where=table["stage"] == EGG).tolist() == [
        int(table["count"][0])
    ]
    table.add(7, stage=EGG, age=1)
    table.merge()
    keys = list(zip(table["stage"].tolist(), table["age"].tolist()))
    assert keys == sorted(set(keys)) and table.total() == before + 7
    assert "cohorts" in repr(table) and len(table.to_dataframe()) == len(table)


def test_device_cohorts_from_a_host_table():
    """from_table copies the live rows of a CohortTable."""
    host = CohortTable(np.random.default_rng(1), stage=np.int8, female=bool)
    host.add([3, 4], stage=[EGG, ADULT], female=[True, False])
    table = DeviceCohortTable.from_table(host, PhiloxStream(SEED))
    assert table["count"].tolist() == [3, 4] and table["female"].tolist() == [
        True,
        False,
    ]


def run_cohort_season(stream, days=40):
    """A small cohort model: thin, age, split and lay for ``days`` days."""
    table = cohorts(stream)
    for _ in range(days):
        table.thin(np.where(table["stage"] == ADULT, 0.9, 0.8))
        table["age"] = table["age"] + 1
        table.split(
            0.3, where=(table["stage"] == EGG) & (table["age"] > 2), stage=ADULT
        )
        laid = int(table.draw(0.5, where=table["stage"] == ADULT).sum())
        table.add(laid * 3, stage=EGG, age=0)
        table.merge()
    return table


def test_gpu_backends_give_the_numpy_cohorts(other_backend):
    """Same seed, same cohorts after a season, on CuPy and (64-bit) JAX.

    Short: JAX compiles every operation again whenever the table changes size.
    """
    expected = run_cohort_season(PhiloxStream(SEED), SHORT_SEASON).to_dataframe()
    got = run_cohort_season(
        PhiloxStream(SEED, 0, other_backend), SHORT_SEASON
    ).to_dataframe()
    assert got.equals(expected.astype(got.dtypes.to_dict()))
    assert expected["count"].sum() > 0


def test_gpu_device_table_matches_numpy(other_backend):
    """A column phase gives the same columns on numpy and on the GPU backend."""
    _, host = walkers(2_000)

    def phase(table):
        dies = table.draw(np.clip(table.energy / 4_000, 0, 1))
        table.alive = table.xp.where(dies, 0, table.alive)
        return table.to_numpy("alive")

    expected = phase(DeviceTable.from_columns(host, PhiloxStream(SEED)))
    got = phase(DeviceTable.from_columns(host, PhiloxStream(SEED, 0, other_backend)))
    assert np.array_equal(got, expected)
