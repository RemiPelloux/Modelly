"""The model reporters the page plots, read from ``model_vars`` without a DataFrame.

The page asks every frame for the rows it has not seen yet. Building the whole history
into a DataFrame for that is quadratic over a run, so the common case (every value a
plain int or float) is read straight from the collector's lists, checking each value
once. Anything else (a None, a bool, a string, a huge int) takes the DataFrame path,
which decides with pandas which columns are numbers, exactly as before.
"""

from __future__ import annotations

import math
import weakref
from typing import Any

import numpy as np

# Values pandas reads as an int or float column whatever their mix: the fast path.
PLAIN_TYPES = (float, int, np.floating, np.integer)
BOOLEANS = (bool, np.bool_)
INTEGERS = (int, np.integer)
# Python ints outside int64 make pandas fall back to an object column.
INT64_BOUND = 2**63
# What each collector's columns were checked to be: name -> (list, rows checked, plain).
_checked: weakref.WeakKeyDictionary[Any, dict[str, tuple[list, int, bool]]] = (
    weakref.WeakKeyDictionary()
)


def series_rows(model: Any, start: int = 0) -> dict[str, list] | None:
    """The numeric model reporters collected from row ``start`` on, by name, or None."""
    collector = getattr(model, "datacollector", None)
    if collector is None or not getattr(collector, "model_reporters", None):
        return None
    columns = collector.model_vars
    if not columns or not all(
        _plain(collector, name, columns[name]) for name in columns
    ):
        return frame_rows(collector, start)
    lengths = {len(values) for values in columns.values()}
    if len(lengths) != 1 or lengths == {0}:
        return frame_rows(collector, start)
    return {
        str(name): [None if math.isnan(v) else v for v in map(float, values[start:])]
        for name, values in columns.items()
    }


def _plain(collector: Any, name: str, values: list) -> bool:
    """Whether every value of the column is a plain number, checking new rows only."""
    try:
        seen = _checked.setdefault(collector, {})
    except TypeError:  # a collector that cannot be weakly referenced: check it all
        seen = {}
    checked, done, plain = seen.get(name, (None, 0, True))
    if checked is not values or done > len(values):
        done, plain = 0, True
    plain = plain and all(_plain_value(v) for v in values[done:])
    seen[name] = (values, len(values), plain)
    return plain


def _plain_value(value: Any) -> bool:
    """An int or float pandas keeps numeric (not a bool, not a huge int)."""
    if isinstance(value, BOOLEANS) or not isinstance(value, PLAIN_TYPES):
        return False
    return not isinstance(value, INTEGERS) or (-INT64_BOUND <= int(value) < INT64_BOUND)


def frame_rows(collector: Any, start: int) -> dict[str, list] | None:
    """The DataFrame path: pandas picks the numeric columns."""
    frame = collector.get_model_vars_dataframe().select_dtypes("number")
    if frame.empty:
        return None
    rows = frame.iloc[start:].astype(float)
    return {
        str(name): [None if math.isnan(v) else v for v in rows[name].tolist()]
        for name in rows.columns
    }
