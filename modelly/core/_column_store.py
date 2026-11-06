"""The model's column tables: one ``ColumnTable`` per agent class with columns."""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

import numpy as np

from modelly.core.columns import ColumnTable
from modelly.core.storage import IN_MEMORY, InMemory

if TYPE_CHECKING:
    from modelly.core.agent import Agent


class ColumnStore:
    """One ``ColumnTable`` per agent class that declares columns.

    Indexed by the concrete agent class: ``model.columns[MoneyAgent]``.
    """

    # Where the tables made from now on keep their arrays (modelly.core.storage).
    storage: InMemory = IN_MEMORY

    def __init__(self, random: Random, rng: np.random.Generator) -> None:
        """Create an empty store; tables appear when agents register."""
        self._tables: dict[type, ColumnTable] = {}
        self.random = random
        self.rng = rng

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
            specs = agent_class._column_specs
            table = ColumnTable(specs, self.random, self.rng, self.storage)
            self._tables[agent_class] = table
        table.add(agent)

    def unregister(self, agent: Agent) -> None:
        """Free ``agent``'s row (``Agent.remove`` calls its table directly)."""
        self._tables[type(agent)].remove(agent)
