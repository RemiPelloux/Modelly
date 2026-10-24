"""DataRecorder: the default recorder, keeping snapshots in memory."""

from __future__ import annotations

import warnings
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from modelly.data.recorders.base import BaseDataRecorder

if TYPE_CHECKING:
    from modelly.core.model import Model
    from modelly.data.recorders.config import DatasetConfig


# Rough per-row size, in bytes, of a snapshot that is not a NumPy array.
_ESTIMATED_ROW_BYTES = 100


@dataclass
class DatasetStorage:
    """Storage container with sliding window support."""

    blocks: deque = field(default_factory=deque)
    metadata: dict[str, Any] = field(default_factory=dict)
    total_rows: int = 0
    estimated_size_bytes: int = 0


class DataRecorder(BaseDataRecorder):
    """In-memory data recorder (default implementation)."""

    def __init__(
        self,
        model: Model,
        config: dict[str, DatasetConfig | dict[str, Any]] | None = None,
    ):
        """Initialize the recorder and subscribe to model observables."""
        self.storage: dict[str, DatasetStorage] = {}
        super().__init__(model, config)

    def _initialize_dataset_storage(self, dataset_name: str, dataset: Any) -> None:
        """Initialize storage with deque for efficient windowing."""
        config = self.configs[dataset_name]
        maxlen = config.window_size if config.window_size else None

        self.storage[dataset_name] = DatasetStorage(
            blocks=deque(maxlen=maxlen), metadata={"initialized": True}
        )

    def _store_dataset_snapshot(
        self,
        dataset_name: str,
        time: int | float,
        data: Any,
        is_overwrite: bool = False,
    ) -> None:
        """Store data snapshot with automatic window management."""
        storage = self.storage[dataset_name]
        config = self.configs[dataset_name]

        old_data = None
        if is_overwrite and storage.blocks:
            _, old_data = storage.blocks.pop()
        elif config.window_size and len(storage.blocks) >= config.window_size:
            _, old_data = storage.blocks.popleft()

        added_bytes = self._append_block(dataset_name, time, data)

        # Update bookkeeping for evicted data
        if old_data is not None:
            _forget_block(storage, old_data)

        storage.estimated_size_bytes += added_bytes

    def _append_block(self, dataset_name: str, time: int | float, data: Any) -> int:
        """Append one snapshot to the dataset's blocks and return its size in bytes."""
        storage = self.storage[dataset_name]
        match data:
            case np.ndarray():
                if data.size > 0:
                    return self._append_array(dataset_name, time, data)
                return 0
            case list():
                if not data:
                    return 0
                rows, kind = len(data), "agentdataset"
            case dict():
                rows, kind = 1, "modeldataset"
            case _:
                rows, kind = 1, "custom"

        storage.blocks.append((time, data))
        storage.total_rows += rows
        if "type" not in storage.metadata:
            storage.metadata["type"] = kind
            if kind != "custom":
                first = data[0] if kind == "agentdataset" else data
                storage.metadata["columns"] = list(first.keys())
        return rows * _ESTIMATED_ROW_BYTES

    def _append_array(
        self, dataset_name: str, time: int | float, data: np.ndarray
    ) -> int:
        """Append a NumPy snapshot with the agent ids as first column; return its bytes."""
        storage = self.storage[dataset_name]
        dataset = self.registry.datasets[dataset_name]
        ids = getattr(dataset, "agent_ids", None)
        ids_col = ids.reshape(-1, 1)
        data_to_store = np.hstack([ids_col, data])

        data_copy = data_to_store.copy()
        storage.blocks.append((time, data_copy))
        storage.total_rows += len(data_copy)

        if "type" not in storage.metadata:
            storage.metadata["type"] = "numpyagentdataset"
            storage.metadata["dtype"] = data.dtype
            storage.metadata["columns"] = list(dataset._attributes)
        return data_copy.nbytes

    def clear(self, dataset_name: str | None = None) -> None:
        """Clear stored data."""
        if dataset_name is None:
            for storage in self.storage.values():
                storage.blocks.clear()
                storage.total_rows = 0
                storage.estimated_size_bytes = 0
        else:
            if dataset_name not in self.storage:
                raise KeyError(f"Dataset '{dataset_name}' not found")

            storage = self.storage[dataset_name]
            storage.blocks.clear()
            storage.total_rows = 0
            storage.estimated_size_bytes = 0

    def get_table_dataframe(self, name: str) -> pd.DataFrame:
        """Convert stored data to pandas DataFrame."""
        if name not in self.storage:
            raise KeyError(f"Dataset '{name}' not found")
        storage = self.storage[name]
        data_type = storage.metadata.get("type", "unknown")
        if not storage.blocks and data_type == "unknown":
            return pd.DataFrame(columns=["time"])
        match data_type:
            case "numpyagentdataset":
                return self._convert_numpyAgentDataSet(storage)
            case "agentdataset":
                return self._convert_agentDataSet(storage)
            case "modeldataset":
                return self._convert_modelDataSet(storage)
            case _:
                warnings.warn(
                    f"Unknown data type '{data_type}' for '{name}'",
                    RuntimeWarning,
                    stacklevel=2,
                )
                return pd.DataFrame(storage.blocks)

    def _convert_numpyAgentDataSet(self, storage: DatasetStorage) -> pd.DataFrame:
        """Convert numpy array blocks to DataFrame."""
        columns = storage.metadata.get("columns", [])
        if not storage.blocks:
            final_cols = ["agent_id", *columns, "time"]
            return pd.DataFrame(columns=final_cols)

        arrays = []
        times = []
        for time, array in storage.blocks:
            arrays.append(array)
            times.extend([time] * len(array))

        combined_array = np.vstack(arrays)
        df_cols = ["agent_id", *columns]
        df = pd.DataFrame(combined_array, columns=df_cols)
        df["agent_id"] = df["agent_id"].astype(int)
        df["time"] = times
        return df

    def _convert_agentDataSet(self, storage: DatasetStorage) -> pd.DataFrame:
        """Convert list-of-dicts blocks to DataFrame."""
        rows = []
        for time, block in storage.blocks:
            for row in block:
                rows.append({**row, "time": time})

        if not rows:
            return pd.DataFrame(columns=[*storage.metadata.get("columns", []), "time"])

        return pd.DataFrame(rows)

    def _convert_modelDataSet(self, storage: DatasetStorage) -> pd.DataFrame:
        """Convert model dict blocks to DataFrame."""
        if not storage.blocks:
            columns = storage.metadata.get("columns", [])
            return pd.DataFrame(columns=[*columns, "time"])

        rows = [{**data, "time": time} for time, data in storage.blocks]
        return pd.DataFrame(rows)

    def estimate_memory_usage(self) -> float:
        """Estimate current memory usage in MB."""
        total_bytes = sum(s.estimated_size_bytes for s in self.storage.values())
        return total_bytes / (1024 * 1024)

    def summary(self) -> dict[str, Any]:
        """Get collection status summary."""
        return {
            "datasets": len(self.storage),
            "total_rows": sum(s.total_rows for s in self.storage.values()),
            "memory_mb": self.estimate_memory_usage(),
            "datasets_detail": {
                name: {
                    "enabled": self.configs[name].enabled,
                    "interval": self.configs[name].interval,
                    "blocks": len(storage.blocks),
                    "rows": storage.total_rows,
                    "next_collection": self.configs[name]._next_collection,
                    "type": storage.metadata.get("type", "unknown"),
                }
                for name, storage in self.storage.items()
            },
        }

    def __repr__(self) -> str:
        """String representation."""
        memory = f"{self.estimate_memory_usage():.1f}MB" if self.storage else "0MB"
        return (
            f"DataRecorder("
            f"datasets={len(self.storage)}, "
            f"rows={sum(s.total_rows for s in self.storage.values())}, "
            f"memory={memory})"
        )


def _forget_block(storage: DatasetStorage, old_data: Any) -> None:
    """Subtract an evicted block's rows and estimated bytes from the storage totals."""
    match old_data:
        case np.ndarray():
            storage.total_rows -= len(old_data)
            storage.estimated_size_bytes -= old_data.nbytes
        case list():
            storage.total_rows -= len(old_data)
            storage.estimated_size_bytes -= len(old_data) * _ESTIMATED_ROW_BYTES
        case _:
            storage.total_rows -= 1
            storage.estimated_size_bytes -= _ESTIMATED_ROW_BYTES
