"""What a model declares so that it can be split across processes.

A partitionable model sets ``agent_streams = True`` and a class attribute
``partitionable = Partitionable(space=..., phases=..., reporters=...)``, and its
``step`` runs the declared phases (``self.partitionable.step(self)``). Each phase
is one method that every agent (of the phase's types) runs, and the contract is
what makes a split run draw and compute what one process does:

- a phase reads other agents only within its ``radius`` (cells, network hops or
  distance in a continuous space) and writes only the agent running it;
- the outcome of a phase does not depend on the order agents run in, nor on
  the order neighbours are listed (sort them by ``stream_key()`` if it must);
- every draw in a phase comes from the agent's own streams (``self.random``,
  ``self.rng``), never from the model's generators;
- agents move only in phases declared with ``moves=True``, and they migrate to
  the partition that owns their new location after the phase;
- agent attributes hold plain data, not references to agents, cells or the model.

``plan_of`` and the checks of the distributed build refuse a model that
breaks a part of the contract they can see; ``check_independence`` compares a
split run with a single process for whatever they cannot.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from modelly.core.exceptions import ModellyException

if TYPE_CHECKING:
    from modelly.core.model import Model
    from modelly.distributed.reduce import Reducer

ATTRIBUTE = "partitionable"


class PartitionError(ModellyException):
    """A model cannot be split across processes, or a split run broke the contract."""


@dataclass(frozen=True)
class Phase:
    """One phase of a step: every agent (of ``types``) calls ``method``.

    Attributes:
        method: the agent method the phase calls.
        radius: how far the method reads other agents (Chebyshev cells on a grid,
            hops on a network, distance in a continuous space); 0 reads only the
            agent itself and the agents in its own cell.
        moves: whether the method may change the agent's location.
        types: the agent classes that run the phase (exact classes); all agents
            when ``None``.
    """

    method: str
    radius: float = 0
    moves: bool = False
    types: tuple[type, ...] | None = None

    def __post_init__(self) -> None:
        """Refuse a negative radius."""
        if self.radius < 0:
            raise ValueError(f"phase {self.method!r}: radius must be >= 0")


def run_phase(model: Model, phase: Phase) -> None:
    """Call ``phase.method`` on the model's agents (of ``phase.types``)."""
    if phase.types is None:
        model.agents.do(phase.method)
        return
    for kind in phase.types:
        agents = model.agents_by_type.get(kind)
        if agents:
            agents.do(phase.method)


@dataclass(frozen=True)
class Partitionable:
    """The declaration that lets a model be split across processes.

    Attributes:
        space: the name of the model attribute holding the space to split (a
            grid, a ``Network`` or a ``ContinuousSpace``).
        phases: the phases of one step, in order.
        reporters: name to reducer (``Sum``, ``Min``, ``Max``); each reducer's
            function computes a partition's part of the value from its model.
    """

    space: str
    phases: tuple[Phase, ...]
    reporters: Mapping[str, Reducer] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Refuse a declaration without phases."""
        if not self.phases:
            raise ValueError("a partitionable model declares at least one phase")

    def step(self, model: Model) -> None:
        """Run every phase once, in order: the model's ``step`` on one process."""
        for phase in self.phases:
            run_phase(model, phase)

    def report(self, model: Model) -> dict[str, Any]:
        """The reporters' values for one whole model (a single-process run)."""
        return {
            name: reducer.combine([reducer.function(model)])
            for name, reducer in self.reporters.items()
        }


def plan_of(model_class: type) -> Partitionable:
    """The ``Partitionable`` of ``model_class``, after the checks of its class.

    Raises:
        PartitionError: when the class declares none, or does not use agent streams.
    """
    plan = getattr(model_class, ATTRIBUTE, None)
    name = getattr(model_class, "__name__", repr(model_class))
    if not isinstance(plan, Partitionable):
        raise PartitionError(
            f"{name} cannot be split across processes: it declares no "
            f"`{ATTRIBUTE} = Partitionable(space=..., phases=...)`. A split run "
            "needs to know the space to cut and the phases of a step."
        )
    if not getattr(model_class, "agent_streams", False):
        raise PartitionError(
            f"{name} cannot be split across processes: set `agent_streams = True` "
            "so every agent draws from streams of its own, whatever partition it is in."
        )
    return plan
