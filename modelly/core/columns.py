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
attribute is still the cheapest thing to read inside ``step``. Each column is a
fast property on the class (``modelly.core.column_access``).
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING, Any

import numpy as np

from modelly._optional import LazyModule
from modelly.core.agentset import AgentSet
from modelly.core.column_access import WRITE_ERRORS, _default_writer, fast_view
from modelly.core.storage import IN_MEMORY, InMemory, layout, pickled, restored

if TYPE_CHECKING:
    import pandas as pd

    from modelly.core.agent import Agent
else:
    pd = LazyModule("pandas")

INITIAL_CAPACITY = 64
GROWTH_FACTOR = 2
ID_COLUMN = "unique_id"
# Table attributes rebuilt from ``_data`` by ``_refresh_views``, never pickled.
_DERIVED = frozenset({"_views", "_all_views", "_defaults", "_capacity"})


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

    def __init__(
        self,
        specs: dict[str, Column],
        random: Random,
        rng: np.random.Generator,
        storage: InMemory = IN_MEMORY,
    ) -> None:
        """Allocate one array per column plus the unique_id column, in ``storage``."""
        self._specs = specs
        self.random = random
        self.rng = rng
        self._agents: list[Agent] = []
        self._storage = storage
        self._data = storage.allocate_all(layout(specs, ID_COLUMN), INITIAL_CAPACITY)
        self._refresh_views()

    def _refresh_views(self) -> None:
        """Fast views of the arrays, and the defaults as a new row stores them.

        ``_views`` has one view per column in specs order (the column
        properties read it); ``_all_views`` adds the id column first, for the
        row moves of ``remove``. Views and capacity change only when the arrays do.
        """
        data = self._data
        state = self.__dict__
        views = [fast_view(data[name]) for name in self._specs]
        state["_views"] = views
        state["_all_views"] = [fast_view(data[ID_COLUMN]), *views]
        state["_defaults"] = [
            _default_writer(view, data[name], spec.default)
            for view, (name, spec) in zip(views, self._specs.items(), strict=True)
        ]
        state["_capacity"] = data[ID_COLUMN].shape[0]

    def __getstate__(self) -> dict:
        """Drop the memoryviews, which do not pickle; memory-mapped arrays go as rows."""
        state = self.__dict__.items()
        return pickled({k: v for k, v in state if k not in _DERIVED})

    def __setstate__(self, state: dict) -> None:
        """Restore the arrays into the table's storage and rebuild the views."""
        self.__dict__.update(restored(state))
        self._refresh_views()

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
        """Return a view of column ``name``; only reached for non-attribute names."""
        data = self.__dict__.get("_data")
        if data is not None and name in data:
            return data[name][: len(self.__dict__["_agents"])]
        raise AttributeError(f"{type(self).__name__} has no column {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        """Assigning ``table.<column>`` writes the live rows in place.

        That makes the augmented forms safe: ``table.energy -= 1`` reads the
        view, subtracts, and writes the result back into the column.
        """
        data = self.__dict__.get("_data")
        if data is not None and name in data:
            data[name][: len(self.__dict__["_agents"])] = value
            return
        object.__setattr__(self, name, value)

    def where(self, mask: np.ndarray) -> AgentSet:
        """Return the agents whose row is True in ``mask`` as an AgentSet."""
        agents = self._agents
        rows = np.flatnonzero(mask).tolist()
        return AgentSet([agents[row] for row in rows], random=self.random)

    def draw(self, p: float | np.ndarray) -> np.ndarray:
        """One Bernoulli draw per agent from the model's seeded numpy generator.

        ``p`` is a probability or one probability per row. The "reproduce with
        probability p" phase of a step is ``table.do_where(table.draw(p), "spawn")``.
        """
        return self.rng.random(len(self._agents)) < p

    def do_where(self, mask: np.ndarray, method: str, *args, **kwargs) -> int:
        """Call ``method`` on every agent whose row is True in ``mask``; return how many.

        The agents are snapshotted first, so the method may add or remove agents.
        """
        agents = self._agents
        chosen = [agents[row] for row in np.flatnonzero(mask).tolist()]
        for agent in chosen:
            getattr(agent, method)(*args, **kwargs)
        return len(chosen)

    def remove_where(self, mask: np.ndarray) -> int:
        """Remove every agent whose row is True in ``mask``; return how many.

        The "die" phase of a step: ``table.remove_where(table.energy < 0)``. Each
        agent goes through ``agent.remove()``, so spaces and datasets are updated.
        """
        agents = self._agents
        doomed = [agents[row] for row in np.flatnonzero(mask).tolist()]
        for agent in doomed:
            agent.remove()
        return len(doomed)

    def thin(self, name: str, survival: float | np.ndarray) -> np.ndarray:
        """Replace the counts in column ``name`` by Binomial(count, survival) draws.

        For a row of ``count`` identical individuals, each surviving independently
        with probability ``survival``, the number left is Binomial(count, survival)
        (a sum of Bernoulli draws), so one draw per cohort has the individual
        model's law. Returns the live-rows view of the column after the draw.
        """
        counts = self._data[name][: len(self._agents)]
        counts[:] = self.rng.binomial(counts, survival)
        return counts

    def to_dataframe(self) -> pd.DataFrame:
        """Copy the live rows into a DataFrame indexed by ``unique_id``."""
        n = len(self._agents)
        # The constructor copies the rows; the frame never shares the arrays.
        frame = pd.DataFrame(
            {name: arr[:n] for name, arr in self._data.items()}, copy=True
        )
        return frame.set_index(ID_COLUMN)

    def add(self, agent: Agent) -> int:
        """Append a row for ``agent`` (with the column defaults) and return it."""
        agents = self._agents
        row = len(agents)
        if row >= self._capacity:
            self._grow()
        agents.append(agent)
        try:
            self._all_views[0][row] = agent.unique_id
        except WRITE_ERRORS:
            self._data[ID_COLUMN][row] = agent.unique_id
        for view, default in self._defaults:
            view[row] = default
        agent._column_table = self
        agent._column_row = row
        return row

    def remove(self, agent: Agent) -> None:
        """Free ``agent``'s row by moving the last row into it."""
        row = agent._column_row
        agents = self._agents
        last = len(agents) - 1
        if row != last:
            moved = agents[last]
            agents[row] = moved
            moved._column_row = row
            for view in self._all_views:
                view[row] = view[last]
        agents.pop()
        agent._column_row = -1

    def _grow(self) -> None:
        capacity = self._capacity * GROWTH_FACTOR
        columns = layout(self._specs, ID_COLUMN)
        self._data = self._storage.grow_all(self._data, columns, capacity)
        self._refresh_views()

    def __repr__(self) -> str:
        """Return the row count and column names."""
        return f"<ColumnTable {len(self)} rows, columns={self.columns}>"


__all__ = ["Column", "ColumnStore", "ColumnTable"]  # noqa: F822 (see __getattr__)


def __getattr__(name: str) -> Any:
    """``ColumnStore`` lives in ``_column_store``, which imports this module."""
    if name != "ColumnStore":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from modelly.core._column_store import ColumnStore  # noqa: PLC0415

    return ColumnStore
