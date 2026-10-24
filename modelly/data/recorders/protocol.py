"""The DataSet protocol and the attrgetter-based BaseDataSet."""

from __future__ import annotations

import abc
import operator
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from modelly.data.recorders.base import BaseDataRecorder
    from modelly.data.recorders.config import DatasetConfig


@runtime_checkable
class DataSet(Protocol):
    """Protocol for all data collection classes.

    All datasets raise RuntimeError if accessed after being closed.
    """

    name: str

    @property
    def data(self) -> Any:
        """Return collected data."""
        ...

    def close(self):
        """Close the dataset."""
        ...

    def record(
        self, recorder: BaseDataRecorder, configuration: DatasetConfig | None = None
    ) -> DataSet:
        """Record the collected data."""
        ...


class BaseDataSet(abc.ABC):
    """Abstract base class for data sets.

    Args:
       name: the name of the data set
       fields: the fields to collect

    """

    def __init__(
        self,
        name,
        *,
        fields: str | list[str] | None = None,
    ):
        """Initialize a base data set."""
        self.name = name

        if fields is not None:
            if isinstance(fields, str):
                fields = [fields]
        else:
            raise ValueError("please pass one or more fields to collect")

        self._attributes = fields
        self._collector = operator.attrgetter(*self._attributes)
        self._closed = False

    @property
    @abc.abstractmethod
    def data(self):
        """Return the data of the dataset."""
        ...

    def _check_closed(self):
        """Check to see if the data set has been closed."""
        if self._closed:
            raise RuntimeError(f"DataSet '{self.name}' has been closed")

    def close(self):
        """Cleanup and close the data set."""
        if self._closed:
            return
        self._collector = None
        self._closed = True

    def record(
        self, recorder: BaseDataRecorder, configuration: DatasetConfig | None = None
    ) -> DataSet:
        """Record the collected data."""
        recorder.add_dataset(self, configuration=configuration)
        return self
