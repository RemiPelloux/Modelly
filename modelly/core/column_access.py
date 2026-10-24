"""Fast per-agent access to ``Column`` attributes.

A ``Column`` declared on an agent class is replaced on that class by a plain
``property``: the interpreter inlines property getters, which a custom
descriptor never gets. The getter reads the agent's row through a
``memoryview`` of the column's array, which returns a Python ``int``, ``float``
or ``bool`` instead of building a numpy scalar, so the value is cheaper to
read and much cheaper to do arithmetic on. Dtypes a ``memoryview`` cannot index
(strings, objects, complex, datetimes) keep the numpy array.

Measured on CPython 3.15, one access inside a step:

    plain attribute       read  6 ns    += 1  13 ns
    Column, descriptor    read 79 ns    += 1 171 ns
    Column, this module   read 27 ns    += 1  72 ns
"""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Any

import numpy as np

from modelly.core.exceptions import ColumnMissingError

if TYPE_CHECKING:
    from modelly.core.columns import Column

# memoryview assignment is stricter than numpy's (no float into an int column,
# for one): on these errors the write falls back to numpy's own semantics.
_FALLBACK_ERRORS = (TypeError, ValueError, OverflowError)


def fast_view(array: np.ndarray) -> Any:
    """A ``memoryview`` of ``array`` when it indexes to Python scalars, else ``array``."""
    try:
        view = memoryview(array)
        view[0] = view[0]
    except (TypeError, ValueError, NotImplementedError, BufferError, IndexError):
        return array
    return view


def column_property(name: str, position: int, column: Column) -> property:
    """The property installed for column ``name``, at ``position`` in the class's specs."""

    # The getter is the read alone, as fast as it can be. A removed agent's table is a
    # _RemovedTable, whose read raises ColumnMissingError naming the agent. The setter's try
    # costs nothing until it catches: an agent never added to a model has no table, and
    # its first write (in __init__) then says what is missing.
    def get(agent):
        return agent._column_table._views[position][agent._column_row]

    def set_(agent, value):
        try:
            agent._column_table._views[position][agent._column_row] = value
        except _FALLBACK_ERRORS:
            agent._column_table._data[name][agent._column_row] = value
        except AttributeError:
            raise ColumnMissingError(agent, name) from None

    return property(get, set_, doc=repr(column))


class _RaisingColumn:
    """One column of a removed agent: any read or write raises ColumnMissingError."""

    __slots__ = ("_agent", "_name")

    def __init__(self, agent: Any, name: str) -> None:
        """Stand in for column ``name`` of the removed ``agent``."""
        self._agent, self._name = agent, name

    def __getitem__(self, row: int) -> Any:
        """Refuse the read, naming the agent and the column."""
        raise ColumnMissingError(self._agent(), self._name)

    def __setitem__(self, row: int, value: Any) -> None:
        """Refuse the write, naming the agent and the column."""
        raise ColumnMissingError(self._agent(), self._name)


class _RemovedTable:
    """The column table of a removed agent: every column raises ColumnMissingError.

    Set on removal instead of deleting the table, so the getter needs no try block and
    live agents pay nothing for the clear error. It holds a weak reference only (removal
    is a hot path: models remove thousands of agents a step) and builds the raising
    columns when someone actually reads or writes one.
    """

    __slots__ = ("_agent",)

    def __init__(self, agent: Any) -> None:
        """Stand in for the table ``agent`` had before it was removed."""
        self._agent = weakref.ref(agent)

    def _columns(self) -> list[_RaisingColumn]:
        """One raising column per column of the agent's class, in position order."""
        names = type(self._agent())._column_specs
        return [_RaisingColumn(self._agent, name) for name in names]

    @property
    def _views(self) -> list[_RaisingColumn]:
        """The raising columns by position, as the fast getter indexes them."""
        return self._columns()

    @property
    def _data(self) -> dict[str, _RaisingColumn]:
        """The raising columns by name, as the setter's fallback indexes them."""
        return {column._name: column for column in self._columns()}


def collect_column_specs(cls: type) -> dict[str, Column]:
    """The columns of ``cls``: inherited ones first, in MRO order, then its own.

    Agent classes already processed keep their declarations in
    ``_column_specs`` (their attributes are properties by then); other bases,
    such as plain mixins, are scanned for ``Column`` instances.
    """
    from modelly.core.columns import Column  # noqa: PLC0415 - columns imports agentset

    specs: dict[str, Column] = {}
    for base in reversed(cls.__mro__):
        own = vars(base)
        if base is not cls and "_column_specs" in own:
            specs.update(own["_column_specs"])
        else:
            specs.update(
                (key, value) for key, value in own.items() if isinstance(value, Column)
            )
    return specs


def install_column_properties(cls: type, specs: dict[str, Column]) -> None:
    """Replace every column of ``cls`` by its fast property."""
    for position, (name, column) in enumerate(specs.items()):
        setattr(cls, name, column_property(name, position, column))
