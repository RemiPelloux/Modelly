"""The interface and shared algorithms of every agent set."""

from __future__ import annotations

import operator
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, MutableSet
from random import Random
from typing import TYPE_CHECKING, Any, Literal, overload

from modelly.core.agentset._utils import (
    _resolve_per_agent_values,
)
from modelly.core.agentset.groupby import GroupBy
from modelly.core.agentset.selection import SelectionMixin

if TYPE_CHECKING:
    from modelly.core.agent import Agent
    from modelly.core.agentset.weak import AgentSet


class AbstractAgentSet[A: Agent](SelectionMixin[A], ABC, MutableSet[A]):
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

    def agg(
        self, attribute: str, func: Callable | Iterable[Callable]
    ) -> Any | list[Any]:
        """Aggregate an attribute of all agents in the AgentSet using one or more functions.

        Args:
            attribute (str): The name of the attribute to aggregate.
            func (Callable | Iterable[Callable]):
                - If Callable: A single function to apply to the attribute values (e.g., min, max, sum, np.mean)
                - If Iterable: Multiple functions to apply to the attribute values

        Returns:
            Any | [Any, ...]: Result of applying the function(s) to the attribute values.

        Examples:
            # Single function
            avg_energy = model.agents.agg("energy", np.mean)

            # Multiple functions
            min_wealth, max_wealth, total_wealth = model.agents.agg("wealth", [min, max, sum])
        """
        values = self.get(attribute)

        if isinstance(func, Callable):
            return func(values)
        else:
            return [f(values) for f in func]

    @overload
    def get(
        self,
        attr_names: str,
        handle_missing: Literal["error", "default"] = "error",
        default_value: Any = None,
    ) -> list[Any]: ...

    @overload
    def get(
        self,
        attr_names: list[str],
        handle_missing: Literal["error", "default"] = "error",
        default_value: Any = None,
    ) -> list[list[Any]]: ...

    def get(
        self,
        attr_names,
        handle_missing="error",
        default_value=None,
    ):
        """Retrieve the specified attribute(s) from each agent in the AgentSet.

        Args:
            attr_names (str | list[str]): The name(s) of the attribute(s) to retrieve from each agent.
            handle_missing (str, optional): How to handle missing attributes. Can be:
                                            - 'error' (default): raises an AttributeError if attribute is missing.
                                            - 'default': returns the specified default_value.
            default_value (Any, optional): The default value to return if 'handle_missing' is set to 'default'
                                           and the agent does not have the attribute.

        Returns:
            list[Any]: A list with the attribute value for each agent if attr_names is a str.
            list[list[Any]]: A list with a lists of attribute values for each agent if attr_names is a list of str.

        Raises:
            AttributeError: If 'handle_missing' is 'error' and the agent does not have the specified attribute(s).
            ValueError: If an unknown 'handle_missing' option is provided.
        """
        is_single_attr = isinstance(attr_names, str)
        agents = self.to_list()

        if handle_missing == "error":
            if is_single_attr:
                # attrgetter runs the attribute lookups in C
                return list(map(operator.attrgetter(attr_names), agents))
            return [[getattr(agent, attr) for attr in attr_names] for agent in agents]

        elif handle_missing == "default":
            if is_single_attr:
                return [getattr(agent, attr_names, default_value) for agent in agents]
            return [
                [getattr(agent, attr, default_value) for attr in attr_names]
                for agent in agents
            ]

        else:
            raise ValueError(
                f"Unknown handle_missing option: {handle_missing}, "
                "should be one of 'error' or 'default'"
            )

    def set(self, attr_name: str, value: Any) -> AgentSet[A]:
        """Set a specified attribute for the agents in the AgentSet.

        The behavior is derived from ``value`` (the same value-based rule pandas
        uses for column assignment):

        - A ``list``, ``tuple``, ``numpy.ndarray`` or ``pandas.Series`` is treated
          as one value per agent and is assigned element-wise, in iteration order
          (the same order ``get`` uses), so a ``get -> transform -> set``
          round-trip stays consistent. It must have the same length as the
          AgentSet; a length mismatch raises ``ValueError``.
        - Any other value (a scalar, a string, or any non-sequence) is broadcast:
          every agent receives the same value.

        Args:
            attr_name (str): The name of the attribute to set.
            value (Any): The value(s) to assign. See above for how the shape of
                ``value`` selects element-wise vs broadcast assignment.

        Returns:
            AgentSet: The AgentSet instance itself, after setting the attribute.

        Raises:
            ValueError: If ``value`` is a sequence whose length does not match the
                number of agents in the AgentSet.

        Notes:
            A per-agent sequence is recognized by its type (list, tuple, ndarray,
            Series). To assign a single sequence value to every agent, broadcast
            it explicitly, e.g. ``[shared_list] * len(agentset)``.
        """
        agents = self.to_list()
        for agent, agent_value in zip(
            agents, _resolve_per_agent_values(value, len(agents))
        ):
            setattr(agent, attr_name, agent_value)
        return self

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
