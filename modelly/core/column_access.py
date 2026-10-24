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

    # The try blocks cost nothing until they catch (an agent without a row, removed or
    # never added to a model, has no _column_table). The getter closes over ``position``
    # only: the column's name is looked up on failure, so a read costs what it did in 1.2.
    def get(agent):
        try:
            return agent._column_table._views[position][agent._column_row]
        except AttributeError:
            raise ColumnMissingError(agent, _column_name(agent, position)) from None

    def set_(agent, value):
        try:
            agent._column_table._views[position][agent._column_row] = value
        except _FALLBACK_ERRORS:
            agent._column_table._data[name][agent._column_row] = value
        except AttributeError:
            raise ColumnMissingError(agent, name) from None

    return property(get, set_, doc=repr(column))


def _column_name(agent: Any, position: int) -> str:
    """The name of the column at ``position`` among the columns of ``agent``'s class."""
    return list(type(agent)._column_specs)[position]


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
