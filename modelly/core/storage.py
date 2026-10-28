"""Where column arrays live: ordinary memory, or memory-mapped files on disk.

``ColumnTable`` (``model.columns``) and ``CohortTable`` keep each column in one
numpy array that doubles when it fills up. A storage makes those arrays:

* ``InMemory`` (the default): ``numpy.full`` arrays, as before;
* ``MemoryMapped(directory)``: ``numpy.memmap`` files in a fresh folder under
  ``directory``, so a table can hold more rows than the machine has memory. The
  operating system pages rows in and out; a pass over a column reads it from
  disk once the table no longer fits. Growing extends the file in place,
  without copying the rows already written.

    storage = MemoryMapped("/scratch")           # opt in before the first row
    model.columns.storage = storage              # tables made from now on
    cohorts = CohortTable(model.rng, storage=storage, age=np.int16)
    ...
    storage.close()                              # or ``with MemoryMapped(...)``

The folder is deleted by ``close()``, by the ``with`` block, or when the storage
is garbage-collected or the interpreter exits. Object columns cannot live in a
file and stay in memory. Pickling (``Model.save``) writes the rows themselves,
not the file names, and loading copies them into a new folder under the same
directory: a checkpoint therefore needs as much memory as its columns while it
is written and read, since a checkpoint is built in memory.
"""

from __future__ import annotations

import itertools
import shutil
import tempfile
import weakref
from pathlib import Path
from typing import Any

import numpy as np

__all__ = ["InMemory", "MemoryMapped"]  # the rest is the tables' plumbing

FOLDER_PREFIX = "modelly-columns-"
FILE_SUFFIX = ".dat"

Layout = dict[str, tuple[Any, Any]]  # column name -> (dtype, default of new rows)


class InMemory:
    """Column arrays in ordinary memory: ``numpy.full``, grown by copying."""

    def allocate(self, dtype: Any, capacity: int, default: Any) -> np.ndarray:
        """A new column of ``capacity`` rows, all ``default``."""
        return np.full(capacity, default, dtype=dtype)

    def grow(self, array: np.ndarray, capacity: int, default: Any) -> np.ndarray:
        """``array`` extended to ``capacity`` rows, the new ones ``default``."""
        grown = np.full(capacity, default, dtype=array.dtype)
        grown[: array.shape[0]] = array
        return grown

    def adopt(self, array: np.ndarray) -> np.ndarray:
        """An unpickled column, kept as it is."""
        return array

    def allocate_all(self, layout: Layout, capacity: int) -> dict[str, np.ndarray]:
        """One new column per ``name: (dtype, default)`` of ``layout``."""
        return {
            name: self.allocate(dtype, capacity, default)
            for name, (dtype, default) in layout.items()
        }

    def grow_all(
        self, data: dict[str, np.ndarray], layout: Layout, capacity: int
    ) -> dict[str, np.ndarray]:
        """Every column of ``data`` grown to ``capacity``, new rows at their ``layout`` default."""
        return {
            name: self.grow(array, capacity, layout[name][1])
            for name, array in data.items()
        }

    def adopt_all(self, data: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """Unpickled columns moved into this storage."""
        return {name: self.adopt(array) for name, array in data.items()}

    def __repr__(self) -> str:
        """Name the storage."""
        return "InMemory()"


IN_MEMORY = InMemory()


class MemoryMapped(InMemory):
    """Column arrays in ``numpy.memmap`` files in a folder of their own, removed at the end.

    Args:
        directory: where the folder is made (default: the system's temporary
            directory). Use a disk with room for every column at its capacity.
    """

    def __init__(self, directory: str | Path | None = None) -> None:
        """Make a fresh folder under ``directory`` for this storage's files."""
        self.directory = Path(directory) if directory else Path(tempfile.gettempdir())
        self.path = Path(tempfile.mkdtemp(prefix=FOLDER_PREFIX, dir=self.directory))
        self._files = itertools.count()
        self._cleanup = weakref.finalize(self, shutil.rmtree, self.path, True)

    def allocate(self, dtype: Any, capacity: int, default: Any) -> np.ndarray:
        """A new file-backed column of ``capacity`` rows, all ``default``."""
        dtype = np.dtype(dtype)
        if dtype.hasobject or capacity == 0:  # no file for objects, none can be empty
            return super().allocate(dtype, capacity, default)
        file = self.path / f"{next(self._files)}{FILE_SUFFIX}"
        array = np.memmap(file, dtype=dtype, mode="w+", shape=(capacity,))
        if default != 0:  # a new file reads as zeros already
            array[:] = default
        return array

    def grow(self, array: np.ndarray, capacity: int, default: Any) -> np.ndarray:
        """The same file extended to ``capacity`` rows, the new ones ``default``."""
        if not isinstance(array, np.memmap):
            return super().grow(array, capacity, default)
        old = array.shape[0]
        array.flush()
        grown = np.memmap(
            array.filename, dtype=array.dtype, mode="r+", shape=(capacity,)
        )
        if default != 0:
            grown[old:] = default
        return grown

    def adopt(self, array: np.ndarray) -> np.ndarray:
        """An unpickled column copied into a new file of this storage."""
        if array.dtype.hasobject or array.shape[0] == 0:
            return array
        mapped = self.allocate(array.dtype, array.shape[0], 0)
        mapped[:] = array
        return mapped

    def close(self) -> None:
        """Delete the folder and its files. Arrays still mapped keep their pages until dropped."""
        self._cleanup()

    @property
    def closed(self) -> bool:
        """Whether the folder has been deleted."""
        return not self._cleanup.alive

    def __enter__(self) -> MemoryMapped:
        """Use the storage in a ``with`` block; the folder goes at its end."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Delete the folder."""
        self.close()

    def __reduce__(self) -> tuple:
        """Unpickle as a new folder under the same directory (the rows travel with the tables)."""
        return type(self), (self.directory,)

    def __repr__(self) -> str:
        """The folder the files are in."""
        return f"MemoryMapped({str(self.path)!r})"


def layout(specs: dict[str, Any], id_column: str) -> Layout:
    """The layout of a ``ColumnTable``: its int64 id column, then each ``Column``'s."""
    columns = {name: (spec.dtype, spec.default) for name, spec in specs.items()}
    return {id_column: (np.int64, 0)} | columns


def pickled(state: dict[str, Any]) -> dict[str, Any]:
    """A table's state with its ``_data`` columns as base-class ndarrays (views, no copy).

    A memory-mapped column then pickles as its rows rather than as a file name.
    """
    data = {
        name: array.view(np.ndarray) if isinstance(array, np.memmap) else array
        for name, array in state["_data"].items()
    }
    return state | {"_data": data}


def restored(state: dict[str, Any]) -> dict[str, Any]:
    """An unpickled table's state with its columns moved into its ``_storage``."""
    storage = state.get("_storage", IN_MEMORY)
    return state | {"_storage": storage, "_data": storage.adopt_all(state["_data"])}
