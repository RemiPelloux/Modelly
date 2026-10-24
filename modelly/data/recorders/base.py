"""BaseDataRecorder for the Custom Data Recorders.

Subclasses must implement:
    - _store_dataset_snapshot: Store a single dataset snapshot
    - _get_dataset_dataframe: Retrieve stored data as DataFrame
    - clear: Clear stored data
    - summary: Return collection status summary

The base class handles:
    - Observable subscription and signal handling
    - Collection interval management
    - Dataset configuration
    - Enable/disable logic


Key Design Principles:
    1. ABC-based design for custom storage backends
    2. Separation of concerns: BaseDataRecorder(owns config) vs CustomRecorder(owns storage)
    3. Observable-based collection
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import pandas as pd

from modelly.data.recorders.config import DatasetConfig
from modelly.time.signals import ModelSignals, ObservableSignals

if TYPE_CHECKING:
    from modelly.core.model import Model
    from modelly.data.recorders.datasets import DataRegistry, DataSet


class BaseDataRecorder(ABC):
    """Base class for data recorders."""

    def __init__(
        self,
        model: Model,
        config: dict[str, DatasetConfig | dict[str, Any]] | None = None,
    ):
        """Initialize the recorder.

        Args:
            model: The model to observe.
            config: Config mapping dataset names to configuration.
                    Values can be dicts or DatasetConfig objects.
        """
        self.model = model
        self.registry: DataRegistry = getattr(model, "data_registry", None)

        if self.registry is None:
            raise AttributeError("Model must have a DataRegistry (model.data_registry)")

        if config is None:
            config = {}

        self.configs: dict[str, DatasetConfig] = (
            self._parse_configs(config) if config else {}
        )

        # Initialize storage for each dataset
        for name in config:
            dataset = self.registry[name]
            self._initialize_dataset_storage(name, dataset)

        self._subscribe_to_model()

    @staticmethod
    def _parse_configs(
        config: dict[str, DatasetConfig | dict[str, Any]],
    ) -> dict[str, DatasetConfig]:
        """Return a private DatasetConfig per dataset name from the user's config."""
        configs: dict[str, DatasetConfig] = {}
        for name, user_cfg in config.items():
            if isinstance(user_cfg, DatasetConfig):
                # Copy to ensure unique state; __post_init__ already ran
                configs[name] = copy.copy(user_cfg)
            else:
                configs[name] = DatasetConfig(**user_cfg)
        return configs

    def _subscribe_to_model(self) -> None:
        """Subscribe to model.time for automatic collection."""
        # Subscribe to observables
        self.model.observe("time", ObservableSignals.CHANGED, self._on_time_change)
        self.model.observe("model", ModelSignals.RUN_ENDED, self._on_run_ended)

    def _on_time_change(self, signal) -> None:
        """Handle time change signal."""
        current_time = signal.additional_kwargs.get("old")

        for name, config in self.configs.items():
            is_overwrite = current_time == config._last_collection

            if (
                not config.enabled
                or current_time < config._last_collection
                or (current_time < config._next_collection and not is_overwrite)
            ):
                continue

            dataset = self.registry.datasets[name]
            data_snapshot = dataset.data

            self._store_dataset_snapshot(
                name, current_time, data_snapshot, is_overwrite
            )

            config._last_collection = current_time

            # Update next collection time (may auto-disable)
            if current_time >= config._next_collection:
                config.update_next_collection(current_time)

    def _on_run_ended(self, signal) -> None:
        """Capture the final state when the run finishes."""
        current_time = self.model.time

        for name, config in self.configs.items():
            if not config.enabled or current_time < config._last_collection:
                continue

            is_overwrite = current_time == config._last_collection

            dataset = self.registry.datasets[name]
            self._store_dataset_snapshot(name, current_time, dataset.data, is_overwrite)

            config._last_collection = current_time

    @abstractmethod
    def _initialize_dataset_storage(self, dataset_name: str, dataset: Any) -> None:
        """Initialize storage for a specific dataset."""

    @abstractmethod
    def _store_dataset_snapshot(
        self, dataset_name: str, time: int | float, data: Any
    ) -> None:
        """Store a single snapshot of data."""

    def collect(self) -> None:
        """Manually trigger collection (for manual mode or testing).

        Normally you don't need to call this - it's handled via observables.
        But you can call it manually if needed.
        """
        current_time = self.model.time

        for name, config in self.configs.items():
            if not config.enabled:
                continue

            dataset = self.registry.datasets[name]
            data_snapshot = dataset.data
            self._store_dataset_snapshot(name, current_time, data_snapshot)
            if (current_time - config.start_time) % config.interval == 0:
                config.update_next_collection(current_time)

    @abstractmethod
    def clear(self, dataset_name: str | None = None) -> None:
        """Clear stored data."""

    def enable_dataset(self, dataset_name: str) -> None:
        """Enable collection for a dataset."""
        if dataset_name not in self.configs:
            raise KeyError(f"Dataset '{dataset_name}' not found")
        self.configs[dataset_name].enabled = True

    def disable_dataset(self, dataset_name: str) -> None:
        """Disable collection for a dataset."""
        if dataset_name not in self.configs:
            raise KeyError(f"Dataset '{dataset_name}' not found")
        self.configs[dataset_name].enabled = False

    def add_dataset(
        self, dataset: DataSet, configuration: DatasetConfig | None = None
    ) -> None:
        """Add a dataset to the collection.

        Args:
            dataset (DataSet): Dataset to record
            configuration (DatasetConfig|None): Configuration for recording the dataset

        """
        if configuration is None:
            configuration = DatasetConfig()

        name = dataset.name
        self.configs[name] = copy.copy(configuration)
        self._initialize_dataset_storage(name, dataset)

    @abstractmethod
    def get_table_dataframe(self, name: str) -> pd.DataFrame:
        """Convert stored data to pandas DataFrame."""

    def get_all_dataframes(self) -> dict[str, pd.DataFrame]:
        """Get DataFrames for all datasets."""
        return {name: self.get_table_dataframe(name) for name in self.configs}

    @abstractmethod
    def summary(self) -> dict[str, Any]:
        """Get collection status summary."""
