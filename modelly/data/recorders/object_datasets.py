"""Datasets read from Python objects: agents, the model, and hand-written table rows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from modelly.core.agent import Agent
from modelly.core.agentset import AbstractAgentSet
from modelly.data.recorders.protocol import BaseDataSet

if TYPE_CHECKING:
    from modelly.core.model import Model
    from modelly.data.recorders.base import BaseDataRecorder
    from modelly.data.recorders.config import DatasetConfig
    from modelly.data.recorders.protocol import DataSet


class AgentDataSet[A: Agent](BaseDataSet):
    """Data set for agents data.

    Args:
        name: the name of the data set
        agents: the agents to collect data from
        fields: fields to collect
        use_dirty_flag: if True, enables manual dirty-flag caching optimization.
                        Default is False (always recompute snapshot).
    """

    def __init__(
        self,
        name: str,
        agents: AbstractAgentSet[A],
        *,
        use_dirty_flag: bool = False,
        fields: str | list[str] | None = None,
    ):
        """Init. of AgentDataSet."""
        if fields is None:
            raise ValueError("please pass one or more fields to collect")
        elif isinstance(fields, str):
            fields = [fields]

        super().__init__(name, fields=["unique_id", *fields])
        self.agents = agents

        # Dirty-flag behavior (opt-in only)
        self._use_dirty_flag: bool = use_dirty_flag
        self._is_dirty: bool = True
        self._cache: list[dict[str, Any]] | None = None

    @property
    def data(self) -> list[dict[str, Any]]:
        """Return the data of the dataset."""
        self._check_closed()

        if (not self._use_dirty_flag) or self._is_dirty or self._cache is None:
            snapshot = [
                dict(zip(self._attributes, self._collector(agent)))
                for agent in self.agents
            ]

            if not self._use_dirty_flag:
                return snapshot

            self._cache = snapshot
            self._is_dirty = False

        return self._cache

    def set_dirty_flag(self) -> None:
        """Mark the dataset as dirty.

        Only meaningful if `use_dirty_flag=True`.
        The next access to `.data` will recompute the snapshot.
        """
        self._check_closed()

        if self._use_dirty_flag:
            self._is_dirty = True

    def close(self):
        """Close the data set."""
        super().close()
        self.agents = None
        self._cache = None


class ModelDataSet[M: Model](BaseDataSet):
    """Data set for model data.

    Args:
        name: the name of the data set
        model: the model to collect data from
        fields: the fields to collect.

    """

    def __init__(self, name, model: M, fields: str | list[str] | None = None):
        """Init of ModelDataSet."""
        super().__init__(name, fields=fields)
        self.model = model

    @property
    def data(self) -> dict[str, Any]:
        """Return the data of the dataset."""
        self._check_closed()
        values = self._collector(self.model)
        if len(self._attributes) == 1:
            return {self._attributes[0]: values}
        else:
            return dict(zip(self._attributes, values))

    def close(self):
        """Close the data set."""
        super().close()
        self.model = None


class TableDataSet:
    """A Table DataSet.

    Args:
        name: the name of the data set
        fields: string or list of strings specifying the columns

    fixme: this needs a closer look
        it now follows the datacollector, so you just add
        a row.

    """

    def __init__(self, name, fields: str | list[str] | None = None):
        """Init."""
        self.name = name

        if fields is None:
            raise ValueError("please pass one or more fields to collect")

        self.fields = fields if isinstance(fields, list) else [fields]
        self.rows = []

    def add_row(self, row: dict[str, Any]):
        """Add a row to the table.

        Args:
            row: the row to add

        Raises:
            RuntimeError: if the dataset has been closed
            ValueError: if the row is empty
            ValueError: if the row is missing required fields
            ValueError: if the row contains unexpected fields

        """
        if self.rows is None:
            raise RuntimeError(f"DataSet '{self.name}' has been closed")

        row_keys = set(row)
        fields_set = set(self.fields)

        # Value error if the row provided by the user is empty
        if not row:
            raise ValueError("row is empty")

        # If the row user passed miss the value for required field
        missing = fields_set - row_keys
        if missing:
            raise ValueError("row is missing fields")

        # If the row user passed includes  the unexpected fields
        unexpected = row_keys - fields_set
        if unexpected:
            raise ValueError(f"Row contains unexpected fields: {unexpected}")

        # Adding the row to rows
        row_to_add = {k: row[k] for k in self.fields}
        self.rows.append(row_to_add)

    @property
    def data(self) -> list[dict[str, Any]]:
        """Return the data of the dataset."""
        if self.rows is None:
            raise RuntimeError(f"DataSet '{self.name}' has been closed")
        return self.rows

    def close(self):
        """Close the data set."""
        self.rows = None

    def record(
        self, recorder: BaseDataRecorder, configuration: DatasetConfig | None = None
    ) -> DataSet:
        """Record the collected data."""
        recorder.add_dataset(self, configuration=configuration)
        return self
