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
    """Store collected data in Parquet files."""

    def __init__(
        self,
        model,
        config: dict[str, DatasetConfig | dict[str, Any]] | None = None,
        output_dir: str = ".",
    ):
        """Initialize Parquet storage backend."""
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Buffers for batching writes
        self.buffers: dict[str, list] = {}
        self.buffer_size = _BUFFER_ROWS  # Write every N rows

        super().__init__(model, config)

    def _initialize_dataset_storage(self, dataset_name: str, dataset: Any) -> None:
        """Initialize buffer for dataset."""
        self.buffers[dataset_name] = []

    def _store_dataset_snapshot(
        self,
        dataset_name: str,
        time: int | float,
        data: Any,
        is_overwrite: bool = False,
    ) -> None:
        """Buffer data and write to Parquet when buffer is full."""
        buffer = self.buffers[dataset_name]

        # handle overwrite
        if is_overwrite:
            self._drop_time(dataset_name, time)

        match data:
            case np.ndarray() if data.size > 0:
                buffer.extend(self._array_records(dataset_name, time, data))

            case list() if data:
                buffer.extend([{**row, "time": time} for row in data])

            case dict():
                buffer.append({**data, "time": time})

        # Flush to disk if buffer is full
        if len(buffer) >= self.buffer_size:
            self._flush_buffer(dataset_name)

    def _drop_time(self, dataset_name: str, time: int | float) -> None:
        """Remove the rows recorded at time, from the buffer or else from the file."""
        buffer = self.buffers[dataset_name]
        removed_from_buffer = False
        while buffer and buffer[-1]["time"] == time:
            buffer.pop()
            removed_from_buffer = True

        # If the buffer was empty (flushed), we must remove it from the physical file
        filepath = self.output_dir / f"{dataset_name}.parquet"
        if not removed_from_buffer and filepath.exists():
            df = pd.read_parquet(filepath)
            df = df[df["time"] != time]  # Drop the overwritten rows
            df.to_parquet(filepath, index=False, compression="snappy")

    def _array_records(
        self, dataset_name: str, time: int | float, data: np.ndarray
    ) -> list[dict]:
        """Turn a NumPy snapshot into row records with agent_id and time columns."""
        dataset = self.registry.datasets[dataset_name]
        columns = list(dataset._attributes)
        ids = dataset.agent_ids

        data_to_store = data
        ids_col = ids.reshape(-1, 1)
        data_to_store = np.hstack([ids_col, data])
        columns = ["agent_id", *columns]

        df = pd.DataFrame(data_to_store, columns=columns)
        df["agent_id"] = df["agent_id"].astype(int)
        df["time"] = time
        return df.to_dict("records")

    def _flush_buffer(self, dataset_name: str):
        """Write buffer to Parquet file."""
        buffer = self.buffers[dataset_name]
        if not buffer:
            return

        df = pd.DataFrame(buffer)
        filepath = self.output_dir / f"{dataset_name}.parquet"

        # Append to existing file or create new
        if filepath.exists():
            existing = pd.read_parquet(filepath)
            df = pd.concat([existing, df], ignore_index=True)

        df.to_parquet(filepath, index=False, compression="snappy")
        buffer.clear()

    def get_table_dataframe(self, name: str) -> pd.DataFrame:
        """Read data from Parquet file."""
        if name not in self.buffers:
            raise KeyError(f"Dataset '{name}' not found")

        # Flush any remaining buffered data first
        self._flush_buffer(name)

        filepath = self.output_dir / f"{name}.parquet"
        if not filepath.exists():
            return pd.DataFrame()

        return pd.read_parquet(filepath)

    def clear(self, dataset_name: str | None = None) -> None:
        """Delete Parquet files."""
        if dataset_name is None:
            for name in self.buffers:
                filepath = self.output_dir / f"{name}.parquet"
                if filepath.exists():  # pragma: no cover
                    filepath.unlink()
                self.buffers[name].clear()
        else:
            if dataset_name not in self.buffers:
                raise KeyError(f"Dataset '{dataset_name}' not found")

            filepath = self.output_dir / f"{dataset_name}.parquet"
            if filepath.exists():  # pragma: no cover
                filepath.unlink()
            self.buffers[dataset_name].clear()

    def summary(self) -> dict[str, Any]:
        """Get collection status summary."""
        summary_data = {
            "datasets": len(self.buffers),
            "output_dir": str(self.output_dir),
        }

        for name in self.buffers:
            size_mb, row_count = self._file_stats(name)

            # Add buffered rows
            row_count += len(self.buffers[name])

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
        filepath = self.output_dir / f"{name}.parquet"
        if not filepath.exists():
            return 0, 0
        # Get file size
        size_mb = os.path.getsize(filepath) / _BYTES_PER_MB
        # Get row count
        df = pd.read_parquet(filepath)
        return size_mb, len(df)

    def __del__(self):  # pragma : no cover
        """Flush all buffers on cleanup."""
        with contextlib.suppress(
            RuntimeError, ImportError, NameError, OSError, FileNotFoundError
        ):
            for name in self.buffers:
                self._flush_buffer(name)
