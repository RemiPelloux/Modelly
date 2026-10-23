"""_HardKeyAgentSet: the strong-reference registry owned by Model."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from random import Random
from typing import TYPE_CHECKING, Any

from modelly.agentset._utils import _resolve_random
from modelly.agentset.abstract import AbstractAgentSet
from modelly.agentset.weak import AgentSet

if TYPE_CHECKING:
    from modelly.agent import Agent


class _HardKeyAgentSet[A: Agent](dict, AbstractAgentSet[A]):
    """A collection class that represents an ordered set of agents using strong references.

    It *is* a ``dict`` whose keys are the agents and whose values are always
    ``None``: membership, length and the registry writes performed by
    ``Model.register_agent`` run in C, which matters because a liveness check
    such as ``agent in model.agents`` runs once per agent per step in many
    models. Strong references suit the registries, whose lifecycle is explicit
    (``Agent.__init__`` / ``Agent.remove``).

    CRITICAL SAFETY FEATURE:
        To prevent "Zombie Agents" (memory leaks), any operation that creates a
        subset, view, or copy of this set (like select, shuffle(inplace=False),
        or groupby) returns a standard AgentSet (weak references). This is done
        in one place, ``_view``, so no view is ever built twice.
    """

    def __init__(
        self,
        agents: Iterable[A],
        random: Random | None = None,
    ):
        """Initialize the _HardKeyAgentSet with strong references to agents.

        Args:
            agents (Iterable[Agent]): An iterable of Agent objects to be included in the set.
            random (Random | None): The random number generator for this agent set.
        """
        dict.__init__(self, dict.fromkeys(agents))
        self.random = _resolve_random(random, next(iter(self)) if self else None)

    @property
    def _agents(self) -> dict[A, None]:
        """The backing dict, which is the set itself (kept for older callers)."""
        return self

    def _view(self, agents: Iterable[A]) -> AgentSet[A]:
        # Views never hold strong references.
        return AgentSet(agents, self.random)

    def _update(self, agents: Iterable[A]):
        """Replace the contents of the set."""
        dict.clear(self)
        dict.update(self, dict.fromkeys(agents))
        return self

    # __len__ and __contains__ come from dict, in C. The dict methods that
    # clash with the AgentSet API are overridden with the set semantics.
    __getitem__ = AbstractAgentSet.__getitem__  # index or slice, not key lookup
    get = AbstractAgentSet.get  # attribute values, not dict.get
    pop = AbstractAgentSet.pop  # MutableSet.pop: remove and return one agent

    def __iter__(self) -> Iterator[A]:
        """Iterate over a snapshot, so agents may be added or removed meanwhile."""
        return iter(list(dict.keys(self)))

    def __repr__(self) -> str:
        """Return a concise, programmer-facing representation."""
        return AbstractAgentSet.__repr__(self)

    def __str__(self) -> str:
        """Return a user-facing description."""
        return AbstractAgentSet.__str__(self)

    def __eq__(self, other: object) -> bool:
        """Two sets are equal when they hold the same agents in the same order."""
        if isinstance(other, _HardKeyAgentSet):
            return dict.__eq__(self, other)
        return NotImplemented

    __hash__ = None  # mutable, like every MutableSet

    def to_list(self) -> list[A]:
        """Convert the _HardKeyAgentSet to a list."""
        return list(dict.keys(self))

    def add(self, agent: A):
        """Add an agent to the _HardKeyAgentSet."""
        self[agent] = None

    def discard(self, agent: A):
        """Remove an agent from the _HardKeyAgentSet if it exists."""
        dict.pop(self, agent, None)

    def remove(self, agent: A):
        """Remove an agent from the _HardKeyAgentSet. Raises KeyError if not present."""
        del self[agent]

    def copy(self) -> AgentSet[A]:
        """Return a shallow copy as a standard AgentSet (Weak Refs)."""
        return self._view(dict.keys(self))

    def __copy__(self):
        """Support for copy.copy(). Returns a standard AgentSet."""
        return self.copy()

    def __reduce__(self):
        """Pickle as (agents, random): a dict subclass would otherwise lose ``random``."""
        return (_HardKeyAgentSet, (self.to_list(), self.random))

    def do(self, method: str | Callable, *args, **kwargs) -> _HardKeyAgentSet[A]:
        """Invoke a method on each agent."""
        # Snapshot keys to avoid RuntimeError if agents are removed during iteration,
        # and skip agents that an earlier call removed from the set.
        if isinstance(method, str):
            for agent in list(dict.keys(self)):
                if agent in self:
                    getattr(agent, method)(*args, **kwargs)
        else:
            for agent in list(dict.keys(self)):
                if agent in self:
                    method(agent, *args, **kwargs)
        return self

    def shuffle_do(
        self, method: str | Callable, *args, **kwargs
    ) -> _HardKeyAgentSet[A]:
        """Shuffle and invoke a method on each agent."""
        order = list(dict.keys(self))
        self.random.shuffle(order)

        if isinstance(method, str):
            for agent in order:
                if agent in self:
                    getattr(agent, method)(*args, **kwargs)
        else:
            for agent in order:
                if agent in self:
                    method(agent, *args, **kwargs)
        return self

    def map(self, method: str | Callable, *args, **kwargs) -> list[Any]:
        """Invoke a method and return results."""
        if isinstance(method, str):
            return [
                getattr(agent, method)(*args, **kwargs)
                for agent in list(dict.keys(self))
                if agent in self
            ]
        return [
            method(agent, *args, **kwargs)
            for agent in list(dict.keys(self))
            if agent in self
        ]
