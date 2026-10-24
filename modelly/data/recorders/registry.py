"""DataRegistry: the named datasets a model exposes to its recorders."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from modelly.core.agent import Agent
from modelly.core.agentset import AbstractAgentSet
from modelly.data.recorders.numpy_dataset import NumpyAgentDataSet
from modelly.data.recorders.object_datasets import AgentDataSet, ModelDataSet

if TYPE_CHECKING:
    from modelly.core.model import Model
    from modelly.data.recorders.protocol import DataSet


class DataRegistry:
    """A registry for data sets."""

    def __init__(self):
        """Initialize the registry."""
        self.datasets = {}

    def add_dataset(self, dataset: DataSet):
        """Add a dataset to the registry.

        Args:
            dataset: the dataset to register

        Raises:
            RuntimeError: if a dataset with the same name is already registered

        """
        if dataset.name not in self.datasets:
            self.datasets[dataset.name] = dataset
        else:
            raise RuntimeError(f"Dataset '{dataset.name}' already registered")

    def create_dataset(
        self, dataset_type, name, *args, fields: str | list[str] | None = None, **kwargs
    ) -> DataSet:
        """Create a dataset of the specified type and add it to the registry."""
        dataset = dataset_type(name, *args, fields=fields, **kwargs)
        self.datasets[name] = dataset
        return dataset

    def track_agents(
        self,
        agents: AbstractAgentSet,
        name: str,
        fields: str | list[str] | None = None,
        *,
        use_dirty_flag: bool = False,
    ) -> AgentDataSet:
        """Track the specified fields for the agents in the AgentSet."""
        return self.create_dataset(
            AgentDataSet,
            name,
            agents,
            fields=fields,
            use_dirty_flag=use_dirty_flag,
        )

    def track_model(
        self,
        model: Model,
        name: str,
        fields: str | list[str] | None = None,
    ) -> ModelDataSet:
        """Track the specified fields in the model."""
        return self.create_dataset(ModelDataSet, name, model, fields=fields)

    def track_agents_numpy(
        self,
        agent_type: type[Agent],
        name: str,
        fields: str | list[str] | None = None,
        n: int = 100,
        dtype: np.dtype | type = np.float64,
    ) -> NumpyAgentDataSet:
        """Track agent fields using NumPy storage.

        Args:
            agent_type: The agent class to install properties on
            name: Name of the dataset
            fields: Attribute names to track
            n: Initial capacity
            dtype: NumPy dtype for the array

        Returns:
            The created NumpyAgentDataSet

        """
        dataset = NumpyAgentDataSet(name, agent_type, fields=fields, n=n, dtype=dtype)
        self.datasets[name] = dataset
        return dataset

    def close(self):
        """Close all datasets."""
        for dataset in self.datasets.values():
            dataset.close()

    def __getitem__(self, name: str) -> DataSet:
        """Get a dataset by name."""
        return self.datasets[name]

    def __contains__(self, name: str) -> bool:
        """Check if a dataset exists."""
        return name in self.datasets

    def get(self, name: str, default=None) -> DataSet | None:
        """Get a dataset by name."""
        return self.datasets.get(name, default)

    def __iter__(self):
        """Iterate over datasets."""
        return iter(self.datasets.values())
