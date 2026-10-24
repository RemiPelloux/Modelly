"""Modelly-specific exception hierarchy."""


class ModellyException(Exception):  # noqa: N818
    """Base class for all Modelly-specific exceptions."""


class SpaceException(ModellyException):
    """Base exception for errors in the discrete_space module."""


def agent_label(agent) -> str:
    """``Sheep 12``: the agent's class and unique_id, as a modeller names it."""
    return f"{type(agent).__name__} {getattr(agent, 'unique_id', None)}"


def model_time(agent) -> str:
    """`` at time 3.0``, or an empty string when the agent has no model."""
    time = getattr(getattr(agent, "model", None), "time", None)
    return "" if time is None else f" at time {time}"


class CellFullException(SpaceException):
    """Raised when attempting to add an agent to a cell with no available capacity."""

    def __init__(self, coordinate, agent=None):
        """Initialize the exception.

        Args:
            coordinate: The coordinate tuple of the full cell.
            agent: The agent moved there, named in the message when given.
        """
        self.coordinate = coordinate
        self.agent = agent
        if agent is None:
            super().__init__(f"Cell at coordinate {coordinate} is full.")
            return
        super().__init__(
            f"Cannot move {agent_label(agent)} to the cell at {coordinate}"
            f"{model_time(agent)}: the cell is full."
        )


class AgentMissingException(ModellyException):
    """Raised when attempting to remove an agent that is not in the cell."""

    def __init__(self, agent, coordinate):
        """Initialize the exception.

        Args:
            agent: The agent instance that was expected.
            coordinate: The coordinate tuple of the cell.
        """
        self.agent = agent
        self.coordinate = coordinate
        super().__init__(
            f"{agent_label(agent)} is not in the cell at {coordinate}{model_time(agent)}."
        )


class AgentRemovedError(ModellyException, AttributeError):
    """Raised when ``remove()`` is called on an agent that has left its space.

    An ``AttributeError``: the type these calls raised before the message named the agent.
    """

    def __init__(self, agent, reason: str = "it was already removed"):
        """Initialize the exception.

        Args:
            agent: The agent ``remove()`` was called on.
            reason: Why there is nothing to remove.
        """
        self.agent = agent
        super().__init__(
            f"Cannot remove {agent_label(agent)}{model_time(agent)}: {reason}."
        )


class ColumnMissingError(ModellyException, AttributeError):
    """Raised when a Column attribute is used on an agent that has no row.

    The agent was removed from its model (its row went with it), or its ``__init__``
    never called ``super().__init__(model)``. An ``AttributeError``, as before.
    """

    def __init__(self, agent, column: str):
        """Initialize the exception.

        Args:
            agent: The agent whose column was read or written.
            column: The name of the Column attribute.
        """
        self.agent = agent
        self.column = column
        if hasattr(agent, "model"):
            reason = "it was removed from the model, and its row with it"
        else:
            reason = "it was never added to a model: call super().__init__(model) first"
        super().__init__(
            f"{agent_label(agent)} has no {column!r} value{model_time(agent)}: {reason}."
        )


class CellMissingException(SpaceException):
    """Raised when attempting to access or remove a cell that does not exist."""

    def __init__(self, coordinate):
        """Initialize the exception.

        Args:
            coordinate: The coordinate tuple of the missing cell.
        """
        self.coordinate = coordinate
        super().__init__(f"Cell at coordinate {coordinate} does not exist.")


class ConnectionMissingException(SpaceException):
    """Raised when attempting to disconnect a cell that is not connected."""

    def __init__(self, cell, other):
        """Initialize the exception.

        Args:
            cell: The source cell instance.
            other: The target cell instance that was not connected.
        """
        self.cell = cell
        self.other = other
        super().__init__(
            f"Connection between {cell.coordinate} and {other.coordinate} does not exist."
        )


class TableMissingException(ModellyException, ValueError):  # noqa: N818
    """Raised when attempting to access a table that does not exist in the DataCollector."""

    def __init__(self, table_name):
        """Initialize the exception.

        Args:
            table_name: The name of the missing table.
        """
        self.table_name = table_name
        super().__init__(f"Table '{table_name}' does not exist.")


class DimensionException(ModellyException, ValueError):  # noqa: N818
    """Raised when spatial dimensions do not match expectations or are invalid."""

    def __init__(self, message):
        """Initialize the exception.

        Args:
            message: The error message describing the dimension mismatch.
        """
        super().__init__(message)


class CheckpointError(ModellyException):
    """Raised when a model cannot be saved to, or loaded from, a checkpoint."""
