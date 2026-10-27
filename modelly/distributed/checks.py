"""The checks that refuse a model a split run cannot reproduce, with the reason.

``check_built`` runs on a freshly built model, before it is split: it refuses
what the model's objects show (no such space, agents outside it, column-backed
agents, events of their own, moves into cells with a capacity, phases naming
methods the agents lack). ``Fingerprint`` runs around every phase of a split
run: a phase that drew from the model's generators, or created agents whose
stream key depends on the partition, is refused at the step it happened.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from modelly.core.agent import Agent
from modelly.distributed.contract import Partitionable, PartitionError, Phase

if TYPE_CHECKING:
    from modelly.core.model import Model

# The default schedule of a model keeps one pending event: its next step.
DEFAULT_EVENTS = 1


def _check_agents(model: Model, adapter: Any) -> None:
    """Every agent is in the space and holds no columns or datasets."""
    for kind in model.agent_types:
        if kind.column_specs() or kind._datasets:
            raise PartitionError(
                f"{kind.__name__} keeps Column or dataset state, which a split run "
                "cannot move between partitions yet; use plain attributes"
            )
    for agent in model.agents:
        if not adapter.located(agent):
            raise PartitionError(
                f"{type(agent).__name__} {agent.unique_id} is not in the partitioned "
                "space, so no partition owns it; every agent of a split model has a place"
            )


def _check_phase(model: Model, phase: Phase, capacity: Any) -> None:
    """The phase's agents have its method; a moving phase meets no cell capacity."""
    kinds = phase.types if phase.types is not None else model.agent_types
    for kind in kinds:
        if not callable(getattr(kind, phase.method, None)):
            raise PartitionError(
                f"phase {phase.method!r}: {kind.__name__} has no method of that name"
            )
    if phase.moves and capacity is not None:
        raise PartitionError(
            f"phase {phase.method!r} moves agents into cells with a capacity: who gets "
            "a free cell then depends on the order agents move in, which a split run "
            "cannot reproduce"
        )


def check_built(model: Model, plan: Partitionable, adapter: Any) -> None:
    """Refuse ``model`` when what it built shows it is not partitionable.

    Raises:
        PartitionError: with the reason and what to change.
    """
    if len(model._event_list) > DEFAULT_EVENTS:
        raise PartitionError(
            f"{type(model).__name__} schedules events of its own; a split run steps "
            "the declared phases only"
        )
    _check_agents(model, adapter)
    capacity = getattr(adapter.space, "capacity", None)
    for phase in plan.phases:
        _check_phase(model, phase, capacity)


def space_of(model: Model, plan: Partitionable) -> Any:
    """The space the plan names on ``model``."""
    try:
        return getattr(model, plan.space)
    except AttributeError:
        raise PartitionError(
            f"{type(model).__name__} has no attribute {plan.space!r}, the space its "
            "Partitionable names"
        ) from None


class Fingerprint:
    """What must not change during a phase: the model's generators and id counter."""

    def __init__(self, model: Model) -> None:
        """Remember the state of ``model`` before a phase."""
        self.model = model
        self.random = model.random.getstate()
        self.rng = model.rng.bit_generator.state
        self.counter = model.agent_id_counter

    def check(self, phase: Phase) -> None:
        """Refuse what the phase just did that a split run cannot reproduce.

        Raises:
            PartitionError: if the phase drew from the model's generators, or
                created agents keyed by their partition-dependent ``unique_id``.
        """
        model = self.model
        if model.random.getstate() != self.random or model.rng.bit_generator.state != (
            self.rng
        ):
            raise PartitionError(
                f"phase {phase.method!r} drew from the model's generators (model.random, "
                "model.rng, or a space or cell collection seeded with them); draw from "
                "the agent's own self.random and self.rng instead"
            )
        if model.agent_id_counter != self.counter:
            self._check_births()

    def _check_births(self) -> None:
        """New agents must have a stream key of their own."""
        for agent in self.model.agents:
            default = type(agent).stream_key is Agent.stream_key
            if agent.unique_id >= self.counter and default:
                raise PartitionError(
                    f"{type(agent).__name__} {agent.unique_id} was created during a "
                    "split run and keys its streams on unique_id, which depends on the "
                    "partition; override stream_key() with a key of its own"
                )
