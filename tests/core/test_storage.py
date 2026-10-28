"""Memory-mapped columns hold the same rows as in-memory ones, survive pickling, clean up."""

import gc
import pickle

import numpy as np
import pytest

from modelly import Agent, Column, Model
from modelly.batch.cohorts import CohortTable
from modelly.core.storage import IN_MEMORY, InMemory, MemoryMapped

MILLIONS = 3_000_000  # rows of the on-disk cohort test


class Grazer(Agent):
    """Columns of several dtypes, one of them objects."""

    energy = Column(float, default=2.5)
    age = Column(np.int16, default=1)
    tag = Column("U3", default="ab")
    memo = Column(object, default=None)

    def step(self):
        """Lose energy, age, and sometimes reproduce or die."""
        self.energy -= self.random.random()
        self.age += 1
        if self.energy < 0:
            self.remove()
        elif self.random.random() < 0.3:
            Grazer(self.model)


def grazing(storage=None, steps=12, seed=4):
    """A population that grows past several doublings and shrinks again."""
    model = Model(rng=seed)
    if storage is not None:
        model.columns.storage = storage
    Grazer.create_agents(model, 100)
    for _ in range(steps):
        model.agents.shuffle_do("step")
    return model


def frame(model):
    """The table's live rows as a DataFrame (objects dropped)."""
    return model.columns[Grazer].to_dataframe().drop(columns="memo")


def test_memory_mapped_columns_hold_the_same_rows(tmp_path):
    """Same run, same rows; numeric columns are files in the storage's folder."""
    with MemoryMapped(tmp_path) as storage:
        mapped = grazing(storage)
        table = mapped.columns[Grazer]
        assert len(table) > 100
        assert isinstance(table._data["energy"], np.memmap)
        assert not isinstance(table._data["memo"], np.memmap)  # objects stay in memory
        assert frame(mapped).equals(frame(grazing()))
        assert sorted(storage.path.iterdir())  # the files are there
    assert storage.closed
    assert not storage.path.exists()


def test_default_storage_is_in_memory():
    """Nothing changes for a model that does not opt in."""
    model = grazing(steps=2)
    assert model.columns.storage is IN_MEMORY
    assert type(model.columns[Grazer]._data["energy"]) is np.ndarray


def test_checkpoint_moves_rows_into_a_new_folder(tmp_path):
    """A saved model resumes bit for bit, its columns in a fresh folder."""
    storage = MemoryMapped(tmp_path)
    model = grazing(storage, steps=6)
    path = tmp_path / "run.ckpt"
    model.save(path)
    restored = Model.load(path)
    new_storage = restored.columns.storage
    assert isinstance(new_storage, MemoryMapped)
    assert new_storage.path != storage.path
    assert new_storage.path.parent == tmp_path
    assert restored.columns[Grazer]._storage is new_storage
    for each in (model, restored):
        for _ in range(4):
            each.agents.shuffle_do("step")
    assert frame(restored).equals(frame(model))
    storage.close()
    new_storage.close()


def test_folder_goes_when_the_storage_is_collected(tmp_path):
    """No close(): garbage collection removes the folder."""
    storage = MemoryMapped(tmp_path)
    folder = storage.path
    table = CohortTable(np.random.default_rng(1), storage=storage, stage=np.int8)
    table.add(5, stage=1)
    del table, storage
    gc.collect()
    assert not folder.exists()


def cohort_run(storage: InMemory, rows: int) -> CohortTable:
    """Add, thin, split and compact a large cohort table."""
    rng = np.random.default_rng(11)
    table = CohortTable(rng, storage=storage, stage=np.int8, age=np.int16)
    table.add(rng.integers(0, 50, rows), stage=rng.integers(0, 4, rows), age=0)
    table.thin(0.9)
    table.split(0.25, where=table["stage"] == 1, stage=2)
    table["age"] += 1
    table.compact()
    return table


@pytest.mark.parametrize("rows", [10, MILLIONS])
def test_cohort_table_on_disk_matches_memory(tmp_path, rows):
    """Millions of rows on disk: the same counts as the in-memory table."""
    with MemoryMapped(tmp_path) as storage:
        on_disk = cohort_run(storage, rows)
        in_memory = cohort_run(IN_MEMORY, rows)
        assert len(on_disk) == len(in_memory)
        for name in on_disk.columns:
            assert np.array_equal(on_disk[name], in_memory[name])
        files = sum(f.stat().st_size for f in storage.path.iterdir())
        assert files >= on_disk._data["count"].shape[0] * 8  # the columns are on disk
        restored = pickle.loads(pickle.dumps(on_disk))  # noqa: S301 - written just above
        assert np.array_equal(restored["count"], on_disk["count"])
        assert isinstance(restored._data["count"], np.memmap)
        restored._storage.close()


def test_object_and_empty_columns_stay_in_memory(tmp_path):
    """Objects cannot be mapped; an empty column has no file."""
    with MemoryMapped(tmp_path) as storage:
        assert type(storage.allocate(object, 4, None)) is np.ndarray
        assert type(storage.allocate(float, 0, 0.0)) is np.ndarray
        grown = storage.grow(np.zeros(2), 4, 1.0)
        assert grown.tolist() == [0.0, 0.0, 1.0, 1.0]
