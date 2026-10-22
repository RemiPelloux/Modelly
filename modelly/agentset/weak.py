"""AgentSet: the weak-reference ordered set every view is made of."""

from __future__ import annotations

import contextlib
import weakref
from collections.abc import Callable, Iterable, Iterator
from random import Random
from typing import TYPE_CHECKING, Any

from modelly.agentset._utils import _resolve_random
from modelly.agentset.abstract import AbstractAgentSet

if TYPE_CHECKING:
    from modelly.agent import Agent


class AgentSet[A: Agent](AbstractAgentSet[A]):
    """A collection class that represents an ordered set of agents using weak references.

    This implementation uses weak references to agents, allowing for efficient management
    of agent lifecycles without preventing garbage collection.

    Attributes:
        random (Random): The random number generator for this agent set.

    Notes:
        The AgentSet maintains weak references to agents, which means that agents not
        referenced elsewhere in the program may be automatically removed from the AgentSet.
        This is the default implementation for most use cases where automatic cleanup is desired.

        Internally the set is a plain ``dict`` keyed on ``weakref.ref`` objects (a
        ``weakref.ref`` hashes and compares like its referent while that is alive),
        which is about twice as fast as ``weakref.WeakKeyDictionary`` for
        construction, membership and iteration because it skips that class's
        pure-Python wrapper and iteration guard. Each ref carries a callback that
        drops the entry when its agent is garbage collected. All bulk operations
        walk a snapshot of the keys, never the live dict, so a callback or user
        code mutating the set mid-iteration is always safe.
    """

    def __init__(
        self,
        agents: Iterable[A],
        random: Random | None = None,
    ):
        """Initialize the AgentSet with weak references to agents.

        Args:
            agents (Iterable[Agent]): An iterable of Agent objects to be included in the set.
            random (Random | None): The random number generator for this agent set.
        """
        self._refs: dict[weakref.ReferenceType[A], None] = {}
        self._remove = _make_remover(self)
        self._refs = self._make_refs(agents)
        self.random = _resolve_random(random, self._first_agent())

    # --- internal helpers -------------------------------------------------

    def _make_refs(self, agents: Iterable[A]) -> dict[weakref.ReferenceType[A], None]:
        """Build the ordered ref dict for ``agents`` with this set's removal callback."""
        ref = weakref.ref
        callback = self._remove
        return dict.fromkeys([ref(agent, callback) for agent in agents])

    def _first_agent(self) -> A | None:
        for r in list(self._refs):
            if (agent := r()) is not None:
                return agent
        return None

    def _view(self, agents: Iterable[A]) -> AgentSet[A]:
        # Use type(self) so subclasses of AgentSet get views of their own type.
        return type(self)(agents, self.random)

    def _update(self, agents: Iterable[A]):
        """Update the AgentSet with a new set of agents.

        This is a private method primarily used internally by other methods like select, shuffle, and sort.
        """
        self._refs = self._make_refs(agents)
        return self

    # --- container protocol -----------------------------------------------

    def __len__(self) -> int:
        """Return the number of agents in the AgentSet."""
        return len(self._refs)

    def __iter__(self) -> Iterator[A]:
        """Provide an iterator over the agents in the AgentSet.

        Iterates over a snapshot of the set taken when iteration starts, so the
        set may be modified while iterating. Agents garbage collected during
        iteration are skipped.
        """
        for r in list(self._refs):
            if (agent := r()) is not None:
                yield agent

    def __contains__(self, agent: A) -> bool:
        """Check if an agent is in the AgentSet. Can be used like `agent in agentset`."""
        try:
            return weakref.ref(agent) in self._refs
        except TypeError:  # not weak-referenceable, so it can never be a member
            return False

    def to_list(self) -> list[A]:
        """Convert the AgentSet to a list.

        Returns:
            list[Agent]: A list containing all agents in the AgentSet.

        Notes:
            Use this when you need list operations such as indexing or slicing;
            an AgentSet is an ordered set, not a sequence.
        """
        return [agent for r in list(self._refs) if (agent := r()) is not None]

    def add(self, agent: A):
        """Add an agent to the AgentSet.

        Args:
            agent (Agent): The agent to add to the set.

        Note:
            This method is an implementation of the abstract method from MutableSet.
        """
        # If the agent is already present the dict keeps its existing key, and the
        # fresh ref (with its callback) is simply dropped.
        self._refs[weakref.ref(agent, self._remove)] = None

    def discard(self, agent: A):
        """Remove an agent from the AgentSet if it exists.

        This method does not raise an error if the agent is not present.

        Args:
            agent (Agent): The agent to remove from the set.

        Note:
            This method is an implementation of the abstract method from MutableSet.
        """
        with contextlib.suppress(KeyError):
            del self._refs[weakref.ref(agent)]

    def remove(self, agent: A):
        """Remove an agent from the AgentSet.

        This method raises an error if the agent is not present.

        Args:
            agent (Agent): The agent to remove from the set.

        Note:
            This method is an implementation of the abstract method from MutableSet.
        """
        del self._refs[weakref.ref(agent)]

    # --- bulk operations ----------------------------------------------------

    def do(self, method: str | Callable, *args, **kwargs) -> AgentSet[A]:
        """Invoke a method or function on each agent in the AgentSet.

        Args:
            method (str, callable): the callable to do on each agent

                                        * in case of str, the name of the method to call on each agent.
                                        * in case of callable, the function to be called with each agent as first argument

            *args: Variable length argument list passed to the callable being called.
            **kwargs: Arbitrary keyword arguments passed to the callable being called.

        Returns:
            AgentSet: The AgentSet instance itself.
        """
        # Walk a snapshot of the refs and re-check membership per agent: an earlier
        # agent's call may have removed this agent from the set (or killed it).
        refs = self._refs
        if isinstance(method, str):
            for r in list(refs):
                if (agent := r()) is not None and r in refs:
                    getattr(agent, method)(*args, **kwargs)
        else:
            for r in list(refs):
                if (agent := r()) is not None and r in refs:
                    method(agent, *args, **kwargs)

        return self

    def shuffle_do(self, method: str | Callable, *args, **kwargs) -> AgentSet[A]:
        """Shuffle the agents in the AgentSet and then invoke a method or function on each agent.

        It's a fast, optimized version of calling shuffle() followed by do().
        """
        refs = self._refs
        order = list(refs)
        self.random.shuffle(order)

        if isinstance(method, str):
            for r in order:
                if (agent := r()) is not None and r in refs:
                    getattr(agent, method)(*args, **kwargs)
        else:
            for r in order:
                if (agent := r()) is not None and r in refs:
                    method(agent, *args, **kwargs)

        return self

    def map(self, method: str | Callable, *args, **kwargs) -> list[Any]:
        """Invoke a method or function on each agent in the AgentSet and return the results.

        Args:
            method (str, callable): the callable to apply on each agent

                                        * in case of str, the name of the method to call on each agent.
                                        * in case of callable, the function to be called with each agent as first argument

            *args: Variable length argument list passed to the callable being called.
            **kwargs: Arbitrary keyword arguments passed to the callable being called.

        Returns:
           list[Any]: The results of the callable calls
        """
        refs = self._refs
        if isinstance(method, str):
            return [
                getattr(agent, method)(*args, **kwargs)
                for r in list(refs)
                if (agent := r()) is not None and r in refs
            ]
        return [
            method(agent, *args, **kwargs)
            for r in list(refs)
            if (agent := r()) is not None and r in refs
        ]

    # --- pickling -------------------------------------------------------------

    def __getstate__(self):
        """Retrieve the state of the AgentSet for serialization.

        Returns:
            dict: A dictionary representing the state of the AgentSet.
        """
        return {"agents": self.to_list(), "random": self.random}

    def __setstate__(self, state):
        """Set the state of the AgentSet during deserialization.

        Args:
            state (dict): A dictionary representing the state to restore.
        """
        self.random = state["random"]
        self._refs = {}
        self._remove = _make_remover(self)
        self._update(state["agents"])


def _make_remover(agentset: AgentSet) -> Callable[[weakref.ReferenceType], None]:
    """Create the weakref callback that drops a dead agent from ``agentset``.

    The callback only holds a weak reference to the set, so a set and its refs
    never form a reference cycle.
    """
    selfref = weakref.ref(agentset)

    def _remove(wr):
        agentset = selfref()
        if agentset is not None:
            agentset._refs.pop(wr, None)

    return _remove
