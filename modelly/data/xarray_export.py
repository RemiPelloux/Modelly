"""xarray export of a DataCollector: time series, gridded snapshots and agent panels.

xarray is optional (``pip install "modelly-abm[xarray]"``) and imported only when an
export is asked for. Every dataset has a ``time`` dimension, the model's time at each
collection, so the model and agent datasets of one run line up and merge:

* ``kind="model"``: one variable per model reporter. A reporter that returns a number is
  a series over ``time``; one that returns an array of the same shape every step (a grid
  of a property layer, a histogram) is stacked into ``(time, ...)``, with its other
  dimensions named by ``dims`` or ``<reporter>_dim0``, ``<reporter>_dim1``...
* ``kind="agent"`` (or ``"agenttype"`` with ``name``): one variable per agent reporter
  over ``(time, AgentID)``; an agent that was not there at a step is NaN.

Example:
    >>> data = to_xarray(model.datacollector)  # doctest: +SKIP
    >>> data["heat"].isel(time=-1).plot()  # doctest: +SKIP
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from modelly._optional import require

__all__ = ["to_xarray"]

EXTRA = "xarray"
TIME = "time"
STEP = "Step"  # the time column of the agent frames
KINDS = ("model", "agent", "agenttype")


def stacked(
    name: str, values: list[Any], dims: Sequence[str] | None
) -> tuple[tuple[str, ...], np.ndarray]:
    """``(dimensions, array)`` of one model reporter's values, the first axis ``time``.

    Raises:
        ValueError: when ``dims`` does not name every dimension after ``time``.
    """
    try:
        array = np.asarray(values)
    except ValueError:  # arrays of different shapes: keep one object per step
        array = np.empty(len(values), dtype=object)
        array[:] = values
    extra = array.ndim - 1
    names = (
        tuple(dims)
        if dims is not None
        else tuple(f"{name}_dim{i}" for i in range(extra))
    )
    if len(names) != extra:
        raise ValueError(
            f"reporter {name!r} has {extra} dimension(s) after time, dims names {len(names)}"
        )
    return (TIME, *names), array


def model_dataset(collector: Any, dims: Mapping[str, Sequence[str]]) -> Any:
    """The model reporters of ``collector`` as an ``xarray.Dataset`` over ``time``."""
    xr = require("xarray", EXTRA)
    variables = {
        name: stacked(name, values, dims.get(name))
        for name, values in collector.model_vars.items()
    }
    return xr.Dataset(variables, coords={TIME: list(collector._collection_steps)})


def to_xarray(
    collector: Any,
    kind: str = "model",
    name: Any = None,
    dims: Mapping[str, Sequence[str]] | None = None,
) -> Any:
    """One collection of ``collector`` as an ``xarray.Dataset``.

    Args:
        collector: a DataCollector.
        kind: ``"model"``, ``"agent"`` or ``"agenttype"``.
        name: the agent class, for ``"agenttype"``.
        dims: for ``"model"``, the names of the dimensions after ``time`` of the
            reporters that return arrays, e.g. ``{"heat": ("x", "y")}``.

    Raises:
        ImportError: when xarray is not installed.
        ValueError: for an unknown ``kind``, or ``dims`` of the wrong length.
    """
    if kind == "model":
        return model_dataset(collector, dims or {})
    if kind == "agent":
        frame = collector.get_agent_vars_dataframe()
    elif kind == "agenttype":
        if name is None:
            raise ValueError("kind='agenttype' needs name=<the agent class>")
        frame = collector.get_agenttype_vars_dataframe(name)
    else:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}, got {kind!r}")
    require("xarray", EXTRA)
    return frame.rename_axis(index={STEP: TIME}).to_xarray()
