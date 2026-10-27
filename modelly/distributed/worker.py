"""One partition of a split run: a model holding the agents of its part of space.

Every worker builds the model from the same scenario, so agents get the
``unique_id`` (and so the default stream key) of the single-process build, then
keeps the agents its partition owns; a model that asks ``owns()`` builds only
those in the first place. A step is the declared phases; around a phase
that looks ``radius`` away, the worker sends copies of its border agents
(ghosts) to its neighbours and receives theirs, and after a phase that moves
agents it sends away those now standing on another partition's ground
(migrants, with their streams). Ghosts exist only during their phase.

The backends call these methods in the same order on every worker, and pass
the bytes between them (``modelly.distributed.groups``).
"""

from __future__ import annotations

import pickle
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from modelly.core.agent import Agent
from modelly.distributed.adapters import adapter_for
from modelly.distributed.building import building
from modelly.distributed.checkpoints import read_part, write_part
from modelly.distributed.checks import Fingerprint, check_built, space_of
from modelly.distributed.codec import decode, encode, rebuild
from modelly.distributed.contract import PartitionError, plan_of, run_phase
from modelly.distributed.reduce import plain, records, states


@dataclass(frozen=True)
class BuildRequest:
    """What a worker needs to start: a model to build, or a checkpoint to load.

    Attributes:
        model_class: the partitionable model class.
        scenario: the scenario, pickled (every worker starts from the same bytes).
        partition: the partition spec (``grid_blocks``, ``graph``, ``kd``).
        index: the partition this worker runs.
        checkpoint: a partition file to restore instead of building.
        digest: the SHA-256 the checkpoint file must have.
    """

    model_class: type | None
    scenario: bytes | None
    partition: Any
    index: int
    checkpoint: str | None = None
    digest: str | None = None


def _layout(spec: Any, space: Any) -> Any:
    """``spec.layout(space)``, refused clearly when the spec does not fit the space."""
    try:
        return spec.layout(space)
    except AttributeError:
        raise PartitionError(
            f"{type(spec).__name__} cannot split a {type(space).__name__}: use "
            "grid_blocks for a grid, graph for a Network and kd for a ContinuousSpace"
        ) from None


def _build(request: BuildRequest) -> tuple[Any, Any]:
    """The model built for partition ``request.index``, and its layout."""
    scenario = pickle.loads(request.scenario)  # noqa: S301 - the caller's own bytes
    with building(request.partition, request.index) as build:
        model = request.model_class(scenario=scenario)
    if build.layout is not None:
        return model, build.layout
    return model, _layout(request.partition, space_of(model, plan_of(type(model))))


class PartitionWorker:
    """The model of one partition and the steps of the exchange protocol."""

    def __init__(self, request: BuildRequest) -> None:
        """Build (or restore) the model, check it, and keep this partition's agents."""
        if request.checkpoint is None:
            self.index = request.index
            self.model, layout = _build(request)
        else:
            path = Path(request.checkpoint)
            self.index, layout, self.model = read_part(path, request.digest)
        self.plan = plan_of(type(self.model))
        self.layout = layout
        self.adapter = adapter_for(space_of(self.model, self.plan), layout, self.index)
        self.ghosts: list[Agent] = []
        own_keys = all(
            k.stream_key is not Agent.stream_key for k in self.model.agent_types
        )
        self.built = (len(self.model.agents), self.model.agent_id_counter, own_keys)
        if request.checkpoint is None:
            check_built(self.model, self.plan, self.adapter)
            self._keep_own()

    def _keep_own(self) -> None:
        """Drop the agents of other partitions, without calling their ``remove``."""
        agents = list(self.model.agents)
        owners = self.adapter.owners(agents)
        for i in np.flatnonzero(owners != self.index).tolist():
            self._discard(agents[i])

    def _discard(self, agent: Agent) -> None:
        """Take ``agent`` out of this partition's model and space."""
        self.model.deregister_agent(agent)
        self.adapter.detach(agent)

    def info(self) -> tuple[int, int, int, bool]:
        """Agents built, agents kept, id counter after the build, own stream keys."""
        built, counter, own_keys = self.built
        return built, len(self.model.agents), counter, own_keys

    def begin_step(self) -> None:
        """Advance the model's time by one step, as its default schedule does."""
        self.model._set_time(self.model.time + 1)

    def ghosts_for(self, phase: int) -> dict[int, bytes]:
        """The ghosts each neighbour needs before ``phase``."""
        radius = self.plan.phases[phase].radius
        location = self.adapter.location
        return {
            other: encode(agents, location, ghost=True)
            for other, agents in self.adapter.outgoing(radius).items()
            if agents
        }

    def accept_ghosts(self, inbox: dict[int, bytes]) -> None:
        """Place the neighbours' ghosts, by sender then in the sender's order."""
        for sender in sorted(inbox):
            for record in decode(inbox[sender]):
                ghost, location = rebuild(record, self.model)
                self.adapter.attach(ghost, location, ghost=True)
                self.ghosts.append(ghost)

    def act(self, phase: int) -> dict[int, bytes]:
        """Run ``phase`` on the local agents; the migrants, for a moving phase."""
        declared = self.plan.phases[phase]
        fingerprint = Fingerprint(self.model)
        run_phase(self.model, declared)
        fingerprint.check(declared)
        for ghost in self.ghosts:
            self.adapter.detach(ghost)
        self.ghosts = []
        return self._emigrate() if declared.moves else {}

    def _emigrate(self) -> dict[int, bytes]:
        """Send away the agents standing on another partition's ground."""
        strangers = self.adapter.strangers(list(self.model.agents))
        leaving: dict[int, list[Agent]] = defaultdict(list)
        if strangers:
            for agent, owner in zip(
                strangers, self.adapter.owners(strangers).tolist(), strict=True
            ):
                leaving[owner].append(agent)
        outbox = {}
        for other in sorted(leaving):
            outbox[other] = encode(leaving[other], self.adapter.location, ghost=False)
            for agent in leaving[other]:
                self._discard(agent)
        return outbox

    def accept_migrants(self, inbox: dict[int, bytes]) -> None:
        """Register the arriving agents, by sender then in the sender's order."""
        for sender in sorted(inbox):
            for record in decode(inbox[sender]):
                agent, location = rebuild(record, self.model)
                unique_id = agent.unique_id
                self.model.register_agent(agent)
                agent.unique_id = unique_id
                self.adapter.attach(agent, location, ghost=False)

    def report(self) -> tuple[float, dict[str, Any]]:
        """The model's time and this partition's part of every reporter."""
        parts = {
            name: plain(reducer.function(self.model))
            for name, reducer in self.plan.reporters.items()
        }
        return float(self.model.time), parts

    def snapshot(self, attributes: tuple[str, ...]) -> list[tuple]:
        """``(stream key, location, *attributes)`` of the local agents."""
        return records(self.model.agents, attributes)

    def states(self) -> list[tuple]:
        """The full state of every local agent (see ``reduce.states``)."""
        return states(self.model.agents)

    def save(self, directory: str) -> dict:
        """Write this partition's checkpoint file; its entry for the index."""
        return write_part(Path(directory), self.index, self.model, self.layout)
