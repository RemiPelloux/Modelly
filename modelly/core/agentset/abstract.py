"""The interface and shared algorithms of every agent set."""

from __future__ import annotations

import operator
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, MutableSet
from random import Random
from typing import TYPE_CHECKING, Any, Literal

from modelly.core.agentset.attributes import AttributeMixin
from modelly.core.agentset.groupby import GroupBy
from modelly.core.agentset.selection import SelectionMixin

if TYPE_CHECKING:
    from modelly.core.agent import Agent
    from modelly.core.agentset.weak import AgentSet


class AbstractAgentSet[A: Agent](
    SelectionMixin[A], AttributeMixin[A], ABC, MutableSet[A]
):
    """An abstract base collection class that represents an ordered set of agents within an agent-based model (ABM).

    This class defines the minimal interface that all AgentSet implementations must follow.
    Subclasses are free to override methods with optimized implementations based on their
    storage mechanism (weak references vs strong references).

    Attributes:
        model (Model): The ABM model instance to which this AbstractAgentSet belongs.
    """

    random: Random

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of agents in the AbstractAgentSet."""
        ...

    @abstractmethod
    def __iter__(self) -> Iterator[A]:
        """Provide an iterator over the agents in the AbstractAgentSet."""
        ...

    @abstractmethod
    def __contains__(self, agent: A) -> bool:
        """Check if an agent is in the AgentSet."""
        ...

    @abstractmethod
    def _update(self, agents: Iterable[A]) -> AbstractAgentSet[A]:
        """Update the AbstractAgentSet A with new set of agents."""
        ...

    @abstractmethod
    def to_list(self) -> list[A]:
        """Convert the AbstractAgentSet to a list.

        Returns:
            list[Agent]: A list containing all agents in the AbstractAgentSet.

        Notes:
            Use this when you need list operations such as indexing or slicing;
            an AgentSet is an ordered set, not a sequence.
        """
        ...

    @abstractmethod
    def _view(self, agents: Iterable[A]) -> AgentSet[A]:
        """Build a new set holding ``agents`` to hand back to the caller.

        Every non-inplace operation (select, shuffle, sort, groupby, ...) goes
        through here, so a subclass controls in one place what its views are.
        """
        ...

    def __getitem__(self, item: int | slice):
        """Return the agent at ``item`` or the list for a slice.

        Agents are materialised in order first, so this is O(n); use
        :meth:`to_list` once when indexing repeatedly.
        """
        return self.to_list()[item]

    def __repr__(self) -> str:
        """Return a concise, programmer-facing representation of the AbstractAgentSet."""
        return f"<{type(self).__name__} ({len(self)} agents)>"

    def __str__(self) -> str:
        """Return a user-facing description of the AbstractAgentSet."""
        return f"{type(self).__name__} with {len(self)} agents"

    @abstractmethod
    def add(self, agent: A):
        """Add an agent to the AbstractAgentSet.

        Args:
            agent (Agent): The agent to add to the set.

        Note:
            This method is an implementation of the abstract method from MutableSet.
        """
        ...

    @abstractmethod
    def discard(self, agent: A):
        """Remove an agent from the AbstractAgentSet if it exists.

        This method does not raise an error if the agent is not present.

        Args:
            agent (Agent): The agent to remove from the set.

        Note:
            This method is an implementation of the abstract method from MutableSet.
        """
        ...

    @abstractmethod
    def remove(self, agent: A):
        """Remove an agent from the AbstractAgentSet.

        Raises:
            An Exception if the agent is not present.

        Args:
            agent (Agent): The agent to remove from the set.

        Note:
            This method is an implementation of the abstract method from MutableSet.
        """
        ...

    def groupby(
        self, by: Callable | str, result_type: Literal["agentset", "list"] = "agentset"
    ) -> GroupBy:
        """Group agents by the specified attribute or return from the callable.

        Args:
            by (Callable, str): used to determine what to group agents by

                                * if ``by`` is a callable, it will be called for each agent and the return is used
                                  for grouping
                                * if ``by`` is a str, it should refer to an attribute on the agent and the value
                                  of this attribute will be used for grouping

            result_type (str, optional): The datatype for the resulting groups {"agentset", "list"}

        Returns:
            GroupBy


        Notes:
            There might be performance benefits to using `result_type='list'` if you don't need the advanced functionality
            of an AbstractAgentSet.
        """
        groups = defaultdict(list)
        key = by if isinstance(by, Callable) else operator.attrgetter(by)

        for agent in self.to_list():
            groups[key(agent)].append(agent)

        if result_type == "agentset":
            return GroupBy({k: self._view(v) for k, v in groups.items()})
        return GroupBy(groups)

    def shuffle(self, inplace: bool = False) -> AbstractAgentSet[A]:
        """Randomly shuffle the order of agents in the AbstractAgentSet.

        Args:
            inplace (bool, optional): If True, shuffles the agents in the current set; otherwise, returns a new shuffled AgentSet. Defaults to False.

        Returns:
            A shuffled set. Returns the current set if inplace is True.

        Note:
            Using inplace = True is more performant
        """
        agents = self.to_list()
        self.random.shuffle(agents)
        return self._update(agents) if inplace else self._view(agents)

    def sort(
        self,
        key: Callable[[A], Any] | str,
        ascending: bool = False,
        inplace: bool = False,
    ) -> AbstractAgentSet[A]:
        """Sort the agents in the AbstractAgentSet based on a specified attribute or custom function.

        Args:
            key (Callable[[Agent], Any] | str): A function or attribute name based on which the agents are sorted.
            ascending (bool, optional): If True, the agents are sorted in ascending order. Defaults to False.
            inplace (bool, optional): If True, sorts the agents in the current set; otherwise, returns a new sorted AgentSet. Defaults to False.

        Returns:
            A sorted set. Returns the current set if inplace is True.
        """
        if isinstance(key, str):
            key = operator.attrgetter(key)

        sorted_agents = sorted(self.to_list(), key=key, reverse=not ascending)
        return self._update(sorted_agents) if inplace else self._view(sorted_agents)

    # Performance-critical methods are left abstract

    @abstractmethod
    def do(self, method: str | Callable, *args, **kwargs) -> AbstractAgentSet[A]:
        """Invoke a method or function on each agent in the AbstractAgentSet."""
        ...

    @abstractmethod
    def shuffle_do(
        self, method: str | Callable, *args, **kwargs
    ) -> AbstractAgentSet[A]:
        """Shuffle the agents in the AbstractAgentSet and then invoke a method or function on each agent."""
        ...

    @abstractmethod
    def map(self, method: str | Callable, *args, **kwargs) -> list[Any]:
        """Invoke a method or function on each agent in the AbstractAgentSet and return the results."""
        ...
