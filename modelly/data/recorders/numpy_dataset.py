"""NumpyAgentDataSet: agent attributes stored as columns of a contiguous NumPy array."""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

import numpy as np

from modelly.core.agent import Agent

if TYPE_CHECKING:
    from modelly.data.recorders.base import BaseDataRecorder
    from modelly.data.recorders.config import DatasetConfig
    from modelly.data.recorders.protocol import DataSet


class NumpyAgentDataSet[A: Agent]:
    """A NumPy array data set for storing agent data.

    Uses swap-with-last removal to keep data contiguous, allowing views.

    Note:
        This class does not inherit from BaseDataSet because it doesn't
        use the attrgetter-based collection mechanism.

    """

    _GROWTH_FACTOR = 2.0
    _MIN_GROWTH = 100

    def __init__(
        self,
        name: str,
        agent_type: type[A],
        fields: str | list[str] | None = None,
        n: int = 100,
        dtype: np.dtype | type = np.float64,
    ):
        """Initialize the dataset.

        Args:
            name: Name of the dataset
            agent_type: The agent class to install properties on
            fields: attribute names to track
            n: Initial capacity
            dtype: NumPy dtype for the array

        Raises:
            ValueError: if no attributes are specified

        """
        if fields is None:
            raise ValueError("please pass one or more fields to collect")
        elif isinstance(fields, str):
            fields = [fields]

        self.name = name
        self._attributes = fields
        self._closed = False
        self.dtype = dtype
        self._index_in_table = f"_index_datatable_{name}"
        self._init_storage(n)

        self.agent_type = agent_type
        if not hasattr(agent_type, "_datasets"):
            agent_type._datasets = set()
        agent_type._datasets.add(self.name)
        agent_type._extra_hooks = True

        self._install_properties()

    def _init_storage(self, n: int) -> None:
        """Allocate the data and id arrays with capacity n, and the index mappings."""
        # Core data storage - always contiguous from 0 to _n_active-1
        self._agent_data: np.ndarray = np.empty(
            (n, len(self._attributes)), dtype=self.dtype
        )
        self._agent_ids: np.ndarray = np.zeros(n, dtype=int)
        self._n_active = 0

        # Mappings - index is always position in _agent_data
        self._index_to_agent: dict[int, A] = {}
        self._agent_to_index: dict[A, int] = {}
        self._attribute_to_index: dict[str, int] = {
            attr: i for i, attr in enumerate(self._attributes)
        }

    def _make_getter_setter(self, attribute_name: str):
        """Generate getter and setter for the specified attribute."""
        j = self._attribute_to_index[attribute_name]
        index_attr = self._index_in_table
        data = self._agent_data

        def getter(agent: A):
            return data[agent.__dict__[index_attr], j]

        def setter(agent: A, value):
            data[agent.__dict__[index_attr], j] = value

        return getter, setter

    def _install_properties(self) -> None:
        """Install properties on the agent class for all attributes."""
        for attr in self._attributes:
            setattr(self.agent_type, attr, property(*self._make_getter_setter(attr)))

    def _expand_storage(self) -> None:
        """Expand the internal array when out of space."""
        current_size = self._agent_data.shape[0]
        growth = max(int(current_size * (self._GROWTH_FACTOR - 1)), self._MIN_GROWTH)
        new_size = current_size + growth

        new_data = np.empty((new_size, len(self._attributes)), dtype=self.dtype)
        new_data[:current_size] = self._agent_data
        self._agent_data = new_data

        new_ids = np.zeros(new_size, dtype=int)
        new_ids[:current_size] = self._agent_ids
        self._agent_ids = new_ids

        # Reinstall properties to capture new array reference
        self._install_properties()

    def _check_closed(self) -> None:
        """Raise if dataset has been closed."""
        if self._closed:
            raise RuntimeError(f"DataSet '{self.name}' has been closed")

    def add_agent(self, agent: A) -> int:
        """Add an agent to the dataset.

        Args:
            agent: The agent to add

        Returns:
            The index assigned to the agent

        Raises:
            RuntimeError if the dataset has been closed.

        """
        self._check_closed()
        index = self._n_active

        # Expand if necessary
        if index >= self._agent_data.shape[0]:
            self._expand_storage()

        # Store index on agent
        agent.__dict__[self._index_in_table] = index

        # Update mappings

        self._agent_ids[index] = agent.unique_id
        self._agent_to_index[agent] = index
        self._index_to_agent[index] = agent
        self._n_active += 1

        return index

    def remove_agent(self, agent: A) -> None:
        """Remove an agent from the dataset using swap-with-last.

        Args:
            agent: The agent to remove

        Raises:
            ValueError if the agent is not in the dataset

        """
        self._check_closed()
        index = agent.__dict__.get(self._index_in_table)
        if index is None:
            raise ValueError("agent not in dataset")

        last_index = self._n_active - 1

        if index != last_index:
            # Swap data row with last active row
            self._agent_data[index] = self._agent_data[last_index]
            self._agent_ids[index] = self._agent_ids[last_index]

            # Update the swapped agent's index
            swapped_agent = self._index_to_agent[last_index]
            swapped_agent.__dict__[self._index_in_table] = index

            self._agent_to_index[swapped_agent] = index
            self._index_to_agent[index] = swapped_agent

        # Remove the agent
        del self._agent_to_index[agent]
        del self._index_to_agent[last_index]
        agent.__dict__.pop(self._index_in_table, None)
        self._n_active -= 1

    @property
    def data(self) -> np.ndarray:
        """Return active agent data as a VIEW (no copy).

        Warning:
            Modifying the returned array modifies the underlying data.

        """
        self._check_closed()
        return self._agent_data[: self._n_active]

    @property
    def data_copy(self) -> np.ndarray:
        """Return a copy of active agent data."""
        self._check_closed()
        return self._agent_data[: self._n_active].copy()

    @property
    def agent_ids(self) -> np.ndarray:
        """Return the agent ids as a view (no copy)."""
        return self._agent_ids[: self._n_active]

    @property
    def active_agents(self) -> list[A]:
        """Return list of all active agents (order matches data rows)."""
        self._check_closed()
        return [self._index_to_agent[i] for i in range(self._n_active)]

    def _reset(self) -> None:
        """Reset the dataset to an empty state."""
        self._agent_to_index.clear()
        self._index_to_agent.clear()
        self._n_active = 0

    def __len__(self) -> int:
        """Return the number of active agents."""
        return self._n_active

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"NumpyAgentDataSet(name={self.name!r}, "
            f"active={self._n_active}, "
            f"capacity={self._agent_data.shape[0]})"
        )

    def close(self) -> None:
        """Close the dataset and remove properties from agent class."""
        if self._closed:
            return

        self._reset()
        # Remove properties from agent class
        for attr in self._attributes:
            with suppress(AttributeError):
                delattr(self.agent_type, attr)
        self._closed = True

    def record(
        self, recorder: BaseDataRecorder, configuration: DatasetConfig | None = None
    ) -> DataSet:
        """Record the collected data."""
        recorder.add_dataset(self, configuration=configuration)
        return self
