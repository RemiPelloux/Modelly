"""Build only a partition's agents: ``owns(model, location)`` in a model's ``__init__``.

By default every worker builds the whole initial population and then keeps its
part, which costs the memory of the whole model in every worker while it builds.
A model can build only what its partition owns instead::

    for key, cell in enumerate(cells):
        if owns(self, cell.coordinate):
            Person(self, cell, key=key)  # stream_key() returns key

``owns`` is always ``True`` in a single process, so the model builds the same
agents there. Agents built this way must override ``stream_key()`` with a key
that does not depend on how many agents the process built (here the index in
the single-process creation order); the build refuses a split model whose
workers built different populations with the default keys. Grid blocks and
graph parts can be asked during the build, as they depend on the space only;
k-d boxes are computed from the built positions, so a ``kd`` split needs the
whole population built.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from modelly.distributed.checks import space_of
from modelly.distributed.contract import PartitionError, plan_of
from modelly.distributed.kdtree import KDPartition


@dataclass
class Build:
    """The partition a worker is building, and its layout once asked for."""

    spec: Any
    index: int
    layout: Any = None


_BUILD: ContextVar[Build | None] = ContextVar("modelly_partition_build", default=None)


@contextmanager
def building(spec: Any, index: int) -> Iterator[Build]:
    """Make ``owns`` answer for partition ``index`` of ``spec`` inside the block."""
    build = Build(spec, index)
    token = _BUILD.set(build)
    try:
        yield build
    finally:
        _BUILD.reset(token)


def owns(model: Any, location: Hashable) -> bool:
    """Whether this process builds the agent at ``location`` (always, on one process).

    Raises:
        PartitionError: for a ``kd`` split, whose boxes need the built positions.
    """
    build = _BUILD.get()
    if build is None:
        return True
    if build.layout is None:
        if isinstance(build.spec, KDPartition):
            raise PartitionError(
                "owns() cannot answer for a kd split: its boxes come from the built "
                "positions, so build every agent and let the split keep its part"
            )
        build.layout = build.spec.layout(space_of(model, plan_of(type(model))))
    return build.layout.owner(location) == build.index
