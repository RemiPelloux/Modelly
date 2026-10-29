"""JSONDataRecorder: snapshots kept as JSON-ready records and saved to .json files."""

from __future__ import annotations

import json
import pathlib
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from modelly.data.recorders.base import BaseDataRecorder

if TYPE_CHECKING:
    from modelly.data.recorders.config import DatasetConfig


class NumpyJSONEncoder(json.JSONEncoder):
    """JSON Encoder that handles Numpy types."""

    def default(self, obj):
        """Convert Numpy types to native Python types."""
        # np.integer and np.floating cover every int and float width (e.g.
        # int8..int64, uint*, float16/float32/float64), so narrower dtypes are
        # not missed.
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class JSONDataRecorder(BaseDataRecorder):
    """Store data as JSON files."""

    def __init__(
        self,
        model,
        config: dict[str, DatasetConfig | dict[str, Any]] | None = None,
        output_dir=".",
    ):
        """Initialize JSON Recorder."""
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, list] = {}
        super().__init__(model, config)

    def _initialize_dataset_storage(self, dataset_name: str, dataset: Any) -> None:
        """Initialize empty list for dataset."""
        self.data[dataset_name] = []

    def _store_dataset_snapshot(
        self,
        dataset_name: str,
        time: int | float,
        data: Any,
        is_overwrite: bool = False,
    ) -> None:
        """Store snapshot as dict."""
        # handle overwrite
        if is_overwrite and self.data[dataset_name]:
            self.data[dataset_name].pop()

        match data:
            case dict():
                self.data[dataset_name].append({"time": time, "data": data})
            case list():
                self.data[dataset_name].append({"time": time, "data": data})
            case np.ndarray():
                rows = self._array_rows(dataset_name, data)
                self.data[dataset_name].append({"time": time, "data": rows})
            case _:
                self.data[dataset_name].append({"time": time, "data": data})

    def _array_rows(self, dataset_name: str, data: np.ndarray) -> list[dict]:
        """A NumPy snapshot as one record per agent, with its agent_id, as the other recorders."""
        dataset = self.registry.datasets[dataset_name]
        columns = list(dataset._attributes)
        ids = dataset.agent_ids.tolist()
        return [
            {"agent_id": agent_id, **dict(zip(columns, row, strict=True))}
            for agent_id, row in zip(ids, data.tolist(), strict=True)
        ]

    def get_table_dataframe(self, name: str) -> pd.DataFrame:
        """Convert stored JSON-like data to DataFrame."""
        if name not in self.data:
            raise KeyError(f"Dataset '{name}' not found")

        records = []
        for snapshot in self.data[name]:
            time = snapshot["time"]
            data = snapshot["data"]
            if isinstance(data, list) and (not data or isinstance(data[0], dict)):
                # one record per agent; an empty snapshot has no rows
                records.extend({**row, "time": time} for row in data)
            elif isinstance(data, dict):
                records.append({**data, "time": time})
            else:
                # Handle scalar or simple list
                records.append({"time": time, "value": data})

        return pd.DataFrame(records) if records else pd.DataFrame()

    def clear(self, dataset_name: str | None = None) -> None:
        """Clear data."""
        if dataset_name is None:
            self.data.clear()
        else:
            if dataset_name in self.data:
                self.data[dataset_name].clear()

    def summary(self) -> dict[str, Any]:
        """Get summary."""
        return {
            "datasets": len(self.data),
            "output_dir": str(self.output_dir),
            "details": {
                name: {
                    "snapshots": len(snapshots),
                    "enabled": self.configs[name].enabled,
                }
                for name, snapshots in self.data.items()
            },
        }

    def save_to_json(self):
        """Save all data to JSON files."""
        for name, snapshots in self.data.items():
            filepath = self.output_dir / f"{name}.json"
            with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                json.dump(snapshots, f, indent=2, cls=NumpyJSONEncoder)
