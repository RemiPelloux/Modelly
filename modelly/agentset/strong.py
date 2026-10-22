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


class _HardKeyAgentSet[A: Agent](AbstractAgentSet[A]):
    """A collection class that represents an ordered set of agents using strong references.

    This implementation uses strong references (hard keys) to agents, preventing them
    from being garbage collected as long as they remain in the set. This eliminates weak
    reference overhead for Model-managed collections where lifecycle is explicitly controlled.

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
        self._agents: dict[A, None] = dict.fromkeys(agents)
        self.random = _resolve_random(
            random, next(iter(self._agents)) if self._agents else None
        )

    def _view(self, agents: Iterable[A]) -> AgentSet[A]:
        # Views never hold strong references.
        return AgentSet(agents, self.random)

    def _update(self, agents: Iterable[A]):
        """Update the internal strong dictionary."""
        self._agents = dict.fromkeys(agents)
        return self

    def __len__(self) -> int:
        """Return the number of agents in the _HardKeyAgentSet."""
        return len(self._agents)

    def __iter__(self) -> Iterator[A]:
        """Provide an iterator over the agents in the _HardKeyAgentSet."""
        return iter(self._agents.keys())

    def __contains__(self, agent: A) -> bool:
        """Check if an agent is in the _HardKeyAgentSet. Can be used like `agent in agentset`."""
        return agent in self._agents

    def to_list(self) -> list[A]:
        """Convert the _HardKeyAgentSet to a list."""
        return list(self._agents)

    def __getitem__(self, item):
        return self.to_list()[item]

    def add(self, agent: A):
        """Add an agent to the _HardKeyAgentSet."""
        self._agents[agent] = None

    def discard(self, agent: A):
        """Remove an agent from the _HardKeyAgentSet if it exists."""
        self._agents.pop(agent, None)

    def remove(self, agent: A):
        """Remove an agent from the _HardKeyAgentSet. Raises KeyError if not present."""
        del self._agents[agent]

    def copy(self) -> AgentSet[A]:
        """Return a shallow copy as a standard AgentSet (Weak Refs)."""
        return self._view(self._agents)

    def __copy__(self):
        """Support for copy.copy(). Returns a standard AgentSet."""
        return self.copy()

    def do(self, method: str | Callable, *args, **kwargs) -> _HardKeyAgentSet[A]:
        """Invoke a method on each agent."""
        # Snapshot keys to avoid RuntimeError if agents are removed during iteration,
        # and skip agents that an earlier call removed from the set.
        agents = self._agents
        if isinstance(method, str):
            for agent in list(agents):
                if agent in agents:
                    getattr(agent, method)(*args, **kwargs)
        else:
            for agent in list(agents):
                if agent in agents:
                    method(agent, *args, **kwargs)
        return self

    def shuffle_do(
        self, method: str | Callable, *args, **kwargs
    ) -> _HardKeyAgentSet[A]:
        """Shuffle and invoke a method on each agent."""
        agents = self._agents
        order = list(agents)
        self.random.shuffle(order)

        if isinstance(method, str):
            for agent in order:
                if agent in agents:
                    getattr(agent, method)(*args, **kwargs)
        else:
            for agent in order:
                if agent in agents:
                    method(agent, *args, **kwargs)
        return self

    def map(self, method: str | Callable, *args, **kwargs) -> list[Any]:
        """Invoke a method and return results."""
        agents = self._agents
        if isinstance(method, str):
            return [
                getattr(agent, method)(*args, **kwargs)
                for agent in list(agents)
                if agent in agents
            ]
        return [
            method(agent, *args, **kwargs) for agent in list(agents) if agent in agents
        ]
