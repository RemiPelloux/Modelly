"""ParquetDataRecorder: snapshots buffered and written to .parquet files."""

from __future__ import annotations

import contextlib
import os
import pathlib
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from modelly.data.recorders.base import BaseDataRecorder

if TYPE_CHECKING:
    from modelly.data.recorders.config import DatasetConfig

_BYTES_PER_MB = 1024 * 1024
# Buffered rows that trigger a write to disk.
_BUFFER_ROWS = 1000


class ParquetDataRecorder(BaseDataRecorder):
    """Store collected data in Parquet files, one per dataset.

    Snapshots are buffered as DataFrames and written when the buffer holds
    ``buffer_size`` rows or as many rows as the file already has, whichever is more.
    A Parquet file cannot be appended to, so every write rewrites it; letting the
    buffer grow with the file keeps the total work linear in the rows recorded, where
    a fixed buffer made it quadratic. The buffer then holds at most as many rows as
    the file, which a write reads into memory anyway.
    """

    def __init__(
        self,
        model,
        config: dict[str, DatasetConfig | dict[str, Any]] | None = None,
        output_dir: str = ".",
    ):
        """Initialize Parquet storage backend."""
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Buffers for batching writes: one DataFrame per snapshot
        self.buffers: dict[str, list[pd.DataFrame]] = {}
        self.buffer_size = _BUFFER_ROWS  # Write every N rows, at least
        self._buffered_rows: dict[str, int] = {}
        self._written_rows: dict[str, int] = {}

        super().__init__(model, config)

    def _initialize_dataset_storage(self, dataset_name: str, dataset: Any) -> None:
        """Initialize buffer for dataset."""
        self.buffers[dataset_name] = []
        self._buffered_rows[dataset_name] = 0
        self._written_rows[dataset_name] = _parquet_rows(self._path(dataset_name))

    def _path(self, dataset_name: str) -> pathlib.Path:
        """The Parquet file of a dataset."""
        return self.output_dir / f"{dataset_name}.parquet"

    def _store_dataset_snapshot(
        self,
        dataset_name: str,
        time: int | float,
        data: Any,
        is_overwrite: bool = False,
    ) -> None:
        """Buffer data and write to Parquet when buffer is full."""
        # handle overwrite
        if is_overwrite:
            self._drop_time(dataset_name, time)

        frame = self._snapshot_frame(dataset_name, time, data)
        if frame is None:
            return
        self.buffers[dataset_name].append(frame)
        self._buffered_rows[dataset_name] += len(frame)

        threshold = max(self.buffer_size, self._written_rows[dataset_name])
        if self._buffered_rows[dataset_name] >= threshold:
            self._flush_buffer(dataset_name)

    def _snapshot_frame(
        self, dataset_name: str, time: int | float, data: Any
    ) -> pd.DataFrame | None:
        """One snapshot as a DataFrame with a time column, or None when it is empty."""
        match data:
            case np.ndarray() if data.size > 0:
                frame = self._array_frame(dataset_name, data)
            case list() if data:
                frame = pd.DataFrame(data)
            case dict():
                frame = pd.DataFrame([data])
            case _:
                return None
        frame["time"] = time
        return frame

    def _array_frame(self, dataset_name: str, data: np.ndarray) -> pd.DataFrame:
        """A NumPy snapshot as a DataFrame with an agent_id column first."""
        dataset = self.registry.datasets[dataset_name]
        # data is a view of the dataset's live array: copy it before buffering
        frame = pd.DataFrame(data, columns=list(dataset._attributes), copy=True)
        frame.insert(0, "agent_id", dataset.agent_ids.astype(int))
        return frame

    def _drop_time(self, dataset_name: str, time: int | float) -> None:
        """Remove the rows recorded at time, from the buffer or else from the file."""
        buffer = self.buffers[dataset_name]
        removed_from_buffer = False
        while buffer and buffer[-1]["time"].iat[0] == time:
            self._buffered_rows[dataset_name] -= len(buffer.pop())
            removed_from_buffer = True

        # If the buffer was empty (flushed), we must remove it from the physical file
        filepath = self._path(dataset_name)
        if not removed_from_buffer and filepath.exists():
            df = pd.read_parquet(filepath)
            df = df[df["time"] != time]  # Drop the overwritten rows
            df.to_parquet(filepath, index=False, compression="snappy")
            self._written_rows[dataset_name] = len(df)

    def _flush_buffer(self, dataset_name: str):
        """Write buffer to Parquet file."""
        buffer = self.buffers[dataset_name]
        if not buffer:
            return

        frames = buffer
        filepath = self._path(dataset_name)

        # Append to existing file or create new
        if filepath.exists():
            frames = [pd.read_parquet(filepath), *buffer]
        df = pd.concat(frames, ignore_index=True)

        df.to_parquet(filepath, index=False, compression="snappy")
        self._written_rows[dataset_name] = len(df)
        self._buffered_rows[dataset_name] = 0
        buffer.clear()

    def get_table_dataframe(self, name: str) -> pd.DataFrame:
        """Read data from Parquet file."""
        if name not in self.buffers:
            raise KeyError(f"Dataset '{name}' not found")

        # Flush any remaining buffered data first
        self._flush_buffer(name)

        filepath = self._path(name)
        if not filepath.exists():
            return pd.DataFrame()

        return pd.read_parquet(filepath)

    def clear(self, dataset_name: str | None = None) -> None:
        """Delete Parquet files."""
        if dataset_name is not None and dataset_name not in self.buffers:
            raise KeyError(f"Dataset '{dataset_name}' not found")
        names = list(self.buffers) if dataset_name is None else [dataset_name]
        for name in names:
            self._path(name).unlink(missing_ok=True)
            self.buffers[name].clear()
            self._buffered_rows[name] = 0
            self._written_rows[name] = 0

    def summary(self) -> dict[str, Any]:
        """Get collection status summary."""
        summary_data = {
            "datasets": len(self.buffers),
            "output_dir": str(self.output_dir),
        }

        for name in self.buffers:
            size_mb, row_count = self._file_stats(name)

            # Add buffered rows
            row_count += self._buffered_rows[name]

            summary_data[name] = {
                "enabled": self.configs[name].enabled,
                "interval": self.configs[name].interval,
                "rows": row_count,
                "size_mb": size_mb,
                "next_collection": self.configs[name]._next_collection,
            }

        return summary_data

    def _file_stats(self, name: str) -> tuple[float, int]:
        """Return the size in MB and the row count of the dataset's Parquet file."""
        filepath = self._path(name)
        if not filepath.exists():
            return 0, 0
        return os.path.getsize(filepath) / _BYTES_PER_MB, _parquet_rows(filepath)

    def __del__(self):  # pragma : no cover
        """Flush all buffers on cleanup."""
        with contextlib.suppress(
            RuntimeError, ImportError, NameError, OSError, FileNotFoundError
        ):
            for name in self.buffers:
                self._flush_buffer(name)


def _parquet_rows(filepath: pathlib.Path) -> int:
    """The number of rows of a Parquet file, from its footer; 0 when there is no file."""
    if not filepath.exists():
        return 0
    try:
        import pyarrow.parquet as pq  # noqa: PLC0415 - optional, as for pandas' Parquet I/O
    except ImportError:  # pragma: no cover - pandas reads Parquet with fastparquet
        return len(pd.read_parquet(filepath))
    return pq.read_metadata(filepath).num_rows
