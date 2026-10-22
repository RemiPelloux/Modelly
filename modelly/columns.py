"""Columnar agent state: attributes stored in model-owned numpy arrays.

Declare a ``Column`` on an ``Agent`` subclass and that attribute lives in one
numpy array per agent class instead of in each instance's ``__dict__``. The
agent keeps working as an object (``agent.wealth`` reads and writes its own row)
while the model gets a zero-copy view of every agent's value at once::

    class MoneyAgent(Agent):
        wealth = Column(int, default=1)

    table = model.columns[MoneyAgent]
    table.wealth.mean()                    # numpy, no Python loop
    table.wealth[table.wealth > 10] -= 1   # bulk update, in place
    rich = table.where(table.wealth > 10)  # an AgentSet

Rows are in insertion order; removing an agent moves the last row into the
freed slot, so a view is valid until the next add or remove. Use columns for
the attributes you aggregate, filter, record or update in bulk; a plain
attribute is still the cheapest thing to read inside ``step``.
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from modelly.agentset import AgentSet

if TYPE_CHECKING:
    from modelly.agent import Agent

INITIAL_CAPACITY = 64
GROWTH_FACTOR = 2
ID_COLUMN = "unique_id"


class Column:
    """Descriptor declaring an agent attribute stored in a model-owned array.

    Args:
        dtype: numpy dtype of the column.
        default: value every new agent starts with.
    """

    __slots__ = ("default", "dtype", "name")

    def __init__(self, dtype: Any = float, default: Any = 0) -> None:
        """Declare a column with its dtype and the default each new agent gets."""
        self.dtype = np.dtype(dtype)
        self.default = default
        self.name = ""

    def __set_name__(self, owner: type, name: str) -> None:
        """Record the attribute name the column is bound to."""
        self.name = name

    def __get__(self, agent: Agent | None, owner: type | None = None):
        """Read this agent's value, or return the descriptor on class access."""
        if agent is None:
            return self
        return agent._column_table._data[self.name][agent._column_row]

    def __set__(self, agent: Agent, value: Any) -> None:
        """Write this agent's value into its row."""
        agent._column_table._data[self.name][agent._column_row] = value

    def __repr__(self) -> str:
        """Return the dtype and default of the column."""
        return f"Column({self.dtype}, default={self.default!r})"


class ColumnTable:
    """The arrays of one agent class, one row per live agent.

    Attribute access (``table.wealth``) and item access (``table["wealth"]``)
    return a view of the live rows. ``table.unique_id`` is always present.
    """

    def __init__(self, specs: dict[str, Column], random: Random) -> None:
        """Allocate one array per column plus the unique_id column."""
        self._specs = specs
        self.random = random
        self._agents: list[Agent] = []
        self._data: dict[str, np.ndarray] = {
            ID_COLUMN: np.zeros(INITIAL_CAPACITY, dtype=np.int64),
            **{
                name: np.full(INITIAL_CAPACITY, spec.default, dtype=spec.dtype)
                for name, spec in specs.items()
            },
        }

    def __len__(self) -> int:
        """Return the number of live rows."""
        return len(self._agents)

    def __contains__(self, name: str) -> bool:
        """Return whether ``name`` is a column of this table."""
        return name in self._data

    @property
    def columns(self) -> list[str]:
        """Column names, ``unique_id`` first."""
        return list(self._data)

    @property
    def agents(self) -> list[Agent]:
        """The agents in row order (a copy of the list)."""
        return list(self._agents)

    def __getitem__(self, name: str) -> np.ndarray:
        """Return a view of the live rows of column ``name``."""
        return self._data[name][: len(self._agents)]

    def __getattr__(self, name: str) -> np.ndarray:
        """Return a view of column ``name`` (attribute-style access)."""
        # Only reached for names that are not real attributes.
        data = self.__dict__.get("_data")
        if data is not None and name in data:
            return data[name][: len(self.__dict__["_agents"])]
        raise AttributeError(f"{type(self).__name__} has no column {name!r}")

    def where(self, mask: np.ndarray) -> AgentSet:
        """Return the agents whose row is True in ``mask`` as an AgentSet."""
        agents = self._agents
        rows = np.flatnonzero(mask).tolist()
        return AgentSet([agents[row] for row in rows], random=self.random)

    def to_dataframe(self) -> pd.DataFrame:
        """Copy the live rows into a DataFrame indexed by ``unique_id``."""
        n = len(self._agents)
        frame = pd.DataFrame({name: arr[:n].copy() for name, arr in self._data.items()})
        return frame.set_index(ID_COLUMN)

    def add(self, agent: Agent) -> int:
        """Append a row for ``agent`` (with the column defaults) and return it."""
        row = len(self._agents)
        if row >= self._data[ID_COLUMN].shape[0]:
            self._grow()
        self._agents.append(agent)
        self._data[ID_COLUMN][row] = agent.unique_id
        for name, spec in self._specs.items():
            self._data[name][row] = spec.default
        agent._column_table = self
        agent._column_row = row
        return row

    def remove(self, agent: Agent) -> None:
        """Free ``agent``'s row by moving the last row into it."""
        row = agent._column_row
        last = len(self._agents) - 1
        if row != last:
            moved = self._agents[last]
            self._agents[row] = moved
            moved._column_row = row
            for arr in self._data.values():
                arr[row] = arr[last]
        self._agents.pop()
        agent._column_row = -1

    def _grow(self) -> None:
        old_capacity = self._data[ID_COLUMN].shape[0]
        capacity = old_capacity * GROWTH_FACTOR
        for name, arr in self._data.items():
            default = self._specs[name].default if name in self._specs else 0
            grown = np.full(capacity, default, dtype=arr.dtype)
            grown[:old_capacity] = arr
            self._data[name] = grown

    def __repr__(self) -> str:
        """Return the row count and column names."""
        return f"<ColumnTable {len(self)} rows, columns={self.columns}>"


class ColumnStore:
    """One ``ColumnTable`` per agent class that declares columns.

    Indexed by the concrete agent class: ``model.columns[MoneyAgent]``.
    """

    def __init__(self, random: Random) -> None:
        """Create an empty store; tables appear when agents register."""
        self._tables: dict[type, ColumnTable] = {}
        self.random = random

    def __getitem__(self, agent_class: type) -> ColumnTable:
        """Return the table of ``agent_class``; KeyError if it has none."""
        try:
            return self._tables[agent_class]
        except KeyError as e:
            raise KeyError(
                f"{agent_class.__name__} has no column table: declare at least one "
                "Column on the class and create an agent first."
            ) from e

    def __contains__(self, agent_class: type) -> bool:
        """Return whether ``agent_class`` has a table."""
        return agent_class in self._tables

    def __iter__(self):
        """Iterate over the agent classes that have a table."""
        return iter(self._tables)

    def __len__(self) -> int:
        """Return the number of tables."""
        return len(self._tables)

    def register(self, agent: Agent) -> None:
        """Give ``agent`` a row in its class's table, creating the table if needed."""
        agent_class = type(agent)
        table = self._tables.get(agent_class)
        if table is None:
            table = ColumnTable(agent_class._column_specs, self.random)
            self._tables[agent_class] = table
        table.add(agent)

    def unregister(self, agent: Agent) -> None:
        """Free ``agent``'s row."""
        self._tables[type(agent)].remove(agent)
