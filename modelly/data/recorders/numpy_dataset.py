"""NumpyAgentDataSet: agent attributes stored as columns of a contiguous NumPy array."""

from __future__ import annotations

import weakref
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

    The fields become properties of the agent class. Each agent keeps a reference
    to its own dataset next to its row index, and the properties read through it,
    so models of the same agent class alive at once (or a model and its copy from
    ``Model.load``) each read and write their own array.

    Note:
        This class does not inherit from BaseDataSet because it doesn't
        use the attrgetter-based collection mechanism.

    """

    _GROWTH_FACTOR = 2.0
    _MIN_GROWTH = 100
    # Open datasets per agent class and dataset name, held weakly: a class keeps the
    # properties while one is open (several models, or a model and its loaded copy).
    _OPEN = "_numpy_datasets_open"

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
        self._dataset_in_agent = f"_datatable_{name}"
        self._init_storage(n)

        self.agent_type = agent_type
        self._attach_to_class()

    def _attach_to_class(self) -> None:
        """Register the dataset on its agent class and install the field properties."""
        agent_type = self.agent_type
        if not hasattr(agent_type, "_datasets"):
            agent_type._datasets = set()
        agent_type._datasets.add(self.name)
        agent_type._extra_hooks = True
        opened = vars(agent_type).get(self._OPEN)
        if opened is None:
            opened = {}
            setattr(agent_type, self._OPEN, opened)
        opened.setdefault(self.name, weakref.WeakSet()).add(self)
        self._install_properties()

    def __setstate__(self, state: dict) -> None:
        """Restore a pickled dataset; an open one puts its properties back on the class."""
        self.__dict__.update(state)
        if "_dataset_in_agent" not in state:
            # A checkpoint of 1.4.1 or earlier: its agents hold only their row index.
            self._dataset_in_agent = f"_datatable_{self.name}"
            for agent in self._index_to_agent.values():
                agent.__dict__[self._dataset_in_agent] = self
        if not self._closed:
            self._attach_to_class()

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
        dataset_attr = self._dataset_in_agent

        def getter(agent: A):
            state = agent.__dict__
            return state[dataset_attr]._agent_data[state[index_attr], j]

        def setter(agent: A, value):
            state = agent.__dict__
            state[dataset_attr]._agent_data[state[index_attr], j] = value

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

        # Store the dataset and the index on the agent, for its field properties
        agent.__dict__[self._dataset_in_agent] = self
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
        agent.__dict__.pop(self._dataset_in_agent, None)
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
        """Close the dataset; the last open one of its name removes the class properties."""
        if self._closed:
            return

        self._reset()
        self._closed = True
        opened = vars(self.agent_type).get(self._OPEN, {}).get(self.name)
        if opened is not None:
            opened.discard(self)
            if opened:
                return  # another model's dataset still reads through the properties
        for attr in self._attributes:
            with suppress(AttributeError):
                delattr(self.agent_type, attr)

    def record(
        self, recorder: BaseDataRecorder, configuration: DatasetConfig | None = None
    ) -> DataSet:
        """Record the collected data."""
        recorder.add_dataset(self, configuration=configuration)
        return self
