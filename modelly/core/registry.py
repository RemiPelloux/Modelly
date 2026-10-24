"""The agent registries of a model: ``model.agents`` and ``model.agents_by_type``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from modelly.core.agentset import _HardKeyAgentSet
from modelly.time.signals import ModelSignals

if TYPE_CHECKING:
    from modelly.core.agent import Agent


class AgentRegistry[A: Agent]:
    """Agent registration and lookup for :class:`~modelly.core.model.Model`.

    ``Agent.__init__`` and ``Agent.remove`` inline ``register_agent`` and
    ``deregister_agent`` while a model keeps the defaults (see agent.py).
    """

    def _init_registries(self) -> None:
        """Create the empty per-type and all-agents registries."""
        self._agents_by_type: dict[
            type[A], _HardKeyAgentSet[A]
        ] = {}  # a dict with an agentset for each class of agents
        self._all_agents: _HardKeyAgentSet[A] = _HardKeyAgentSet(
            [], random=self.random
        )  # an agenset with all agents

    def _register_new_type(self, agent: A) -> None:
        """Create the per-type registry for the first agent of a class."""
        self._agents_by_type[type(agent)] = _HardKeyAgentSet(
            [agent], random=self.random
        )

    def _notify_agent_added(self, agent: A) -> None:
        """Emit AGENT_ADDED; reached only when the model is not ``_quiet``."""
        self.notify("agents", ModelSignals.AGENT_ADDED, args=(agent,))

    def _notify_agent_removed(self, agent: A) -> None:
        """Emit AGENT_REMOVED; see _notify_agent_added."""
        self.notify("agents", ModelSignals.AGENT_REMOVED, args=(agent,))

    @property
    def agents(self) -> _HardKeyAgentSet[A]:
        """Provides a _HardKeyAgentSet of all agents in the model, combining agents from all types.

        Returns:
            _HardKeyAgentSet: The agent set containing all agents with strong references.

        Warning:
            This returns the actual internal _HardKeyAgentSet used by Modelly for agent registration
            and tracking. It uses strong references to prevent premature garbage collection and reduce performance overhead
            caused by weak reference management.

            **Do not modify this AgentSet directly** (e.g., by adding or removing agents manually).
            Direct modifications can break the model's agent tracking system and cause unexpected
            behavior. Instead:

            - Use ``Agent()`` to create new agents (automatically registers them)
            - Use ``agent.remove()`` to remove agents (automatically deregisters them)
            - For read-only operations or transformations, work on a copy: ``model.agents.copy()``

        Notes:
            This is Modelly's core agent registration system. All agents created via ``Agent.__init__``
            are automatically registered here.
        """
        return self._all_agents

    @agents.setter
    def agents(self, agents: Any) -> None:
        raise AttributeError(
            "model.agents is managed by Modelly and cannot be assigned. "
            "Use a different attribute name for custom agent storage."
        )

    @property
    def agent_types(self) -> list[type]:
        """Return a list of all unique agent types registered with the model."""
        return list(self._agents_by_type.keys())

    @property
    def agents_by_type(self) -> dict[type[A], _HardKeyAgentSet[A]]:
        """A dictionary where keys are agent types and values are the corresponding _HardKeyAgentSets.

        Returns:
            dict[type[A], _HardKeyAgentSet[A]]: Dictionary mapping agent types to their AgentSets.

        Warning:
            Each AgentSet in this dictionary is a _HardKeyAgentSet with strong references,
            forming part of Modelly's core agent registration system.

            **Do not modify these AgentSets directly**. Direct modifications can break agent
            tracking and cause unexpected behavior. Instead:

            - Use ``Agent()`` to create new agents (automatically registers them)
            - Use ``agent.remove()`` to remove agents (automatically deregisters them)
            - For read-only operations, work on copies: ``model.agents_by_type[AgentType].copy()``

        Notes:
            This is part of Modelly's core agent registration system. All agents are automatically
            registered in the appropriate type-specific AgentSet when created via ``Agent.__init__``.
        """
        return self._agents_by_type

    def register_agent(self, agent: A):
        """Register the agent with the model.

        Args:
            agent: The agent to register.

        Notes:
            This method is called automatically by ``Agent.__init__``, so there
            is no need to use this if you are subclassing Agent and calling its
            super in the ``__init__`` method.
        """
        # The registries' dicts are written directly: this runs on every agent
        # birth, and two method calls per birth were a third of its cost.
        self._all_agents[agent] = None
        agent.unique_id = self.agent_id_counter
        self.agent_id_counter += 1

        # because AgentSet requires model, we cannot use defaultdict
        # tricks with a function won't work because model then cannot be pickled
        try:
            self._agents_by_type[type(agent)][agent] = None
        except KeyError:
            self._register_new_type(agent)
        if (
            self._suppress
            or self._batch_context is not None
            or self.subscribers
            or self._class_subscribers
        ):
            self._notify_agent_added(agent)

    def deregister_agent(self, agent: A):
        """Deregister the agent with the model.

        Args:
            agent: The agent to deregister.

        Notes:
            This method is called automatically by ``Agent.remove``

        """
        del self._agents_by_type[type(agent)][agent]
        del self._all_agents[agent]
        if (
            self._suppress
            or self._batch_context is not None
            or self.subscribers
            or self._class_subscribers
        ):
            self._notify_agent_removed(agent)
