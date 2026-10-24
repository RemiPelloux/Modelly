"""Membership manager for meta-agents."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable
from typing import Any

from modelly.behaviour.meta_agents.backend import MembershipBackend, RelationKey
from modelly.behaviour.meta_agents.combinations import (
    evaluate_combination,
    find_combinations,
)
from modelly.behaviour.meta_agents.meta_agent import (
    _create_meta_agent_instance,
    _deduplicate_preserving_order,
)
from modelly.behaviour.meta_agents.queries import MembershipQueries
from modelly.behaviour.meta_agents.views import MembershipEdge, MembershipView
from modelly.core.agent import Agent
from modelly.time.signals import ModelSignals
from modelly.time.signals.util import Message


def _member_relations(
    agents: Iterable[Any],
    relation: RelationKey,
    memberships: Iterable[tuple[Any, RelationKey]] | None,
) -> tuple[list[Any], list[tuple[Any, RelationKey]]]:
    """Return the deduplicated members and their (member, relation) pairs."""
    if memberships is not None:
        member_relations = list(memberships)
        agents = _deduplicate_preserving_order(member for member, _ in member_relations)
        return agents, member_relations
    agents = _deduplicate_preserving_order(agents)
    return agents, [(agent, relation) for agent in agents]


class MetaAgents(MembershipQueries):
    """Membership manager for agents composed of other agents.

    Tracks who belongs to which group. Change memberships with ``create``,
    ``add_member``, ``remove_member``, ``deactivate``, and ``dissolve``.
    Removing an agent from the model also removes its memberships.
    """

    def __init__(self, model: Any, backend: MembershipBackend | None = None) -> None:
        """Create a membership manager bound to one model."""
        existing_api = getattr(model, "meta_agents", None)
        if existing_api is not None and existing_api is not self:
            raise RuntimeError("Model already has a different membership manager")
        self.model = model
        self.backend = backend or MembershipBackend()
        model.meta_agents = self
        self.model.observe("agents", ModelSignals.AGENT_REMOVED, self._on_agent_removed)

    def _on_agent_removed(self, signal: Message | Any) -> None:
        """Deactivate memberships when a live agent leaves the model."""
        if hasattr(signal, "additional_kwargs"):
            args = signal.additional_kwargs.get("args")
            agent = args[0] if args else signal.additional_kwargs.get("agent")
        else:
            agent = signal
        if agent is not None:
            self.deactivate(agent)

    def _detach_entity(self, entity: Hashable) -> MembershipView:
        """Remove all incident memberships for one entity."""
        snapshot = self.query_memberships(entity)
        self.backend.remove_agent(entity)
        self.backend.remove_group(entity)
        return snapshot

    def create(
        self,
        new_agent_class: str,
        agents: Iterable[Any],
        modelly_agent_type: type[Agent] | None = Agent,
        meta_attributes: dict[str, Any] | None = None,
        meta_methods: dict[str, Callable] | None = None,
        relation: RelationKey = "member",
        memberships: Iterable[tuple[Any, RelationKey]] | None = None,
    ) -> Any:
        """Create a meta-agent group and record its memberships.

        A group is identified by its class name, ``new_agent_class``. When at
        least one of the given agents already belongs to an existing group
        whose class name matches ``new_agent_class``, that group is reused:
        the given agents are added to it and the existing group object is
        returned. Otherwise a new group is created and registered as an agent
        on the model. Note that calling ``create`` with the same class name
        but no overlapping members therefore creates a second, distinct group
        with the same name; name-based lookups (e.g. ``members_of("Team")``)
        then raise because the name is ambiguous. To force a new group, use a
        unique class name (e.g., append a timestamp or UUID). For an example
        see the alliance_formation model.

        Duplicate members are removed, preserving the order of first
        appearance.

        Args:
            new_agent_class: The group's class name. A group with this name is
                reused if any of ``agents`` already belongs to it; otherwise a
                new group with this name is created.
            agents: Initial members of the group.
            modelly_agent_type: Modelly ``Agent`` class used as the base class of the
                group agent. Defaults to ``Agent`` when omitted. Ignored when
                an existing group is reused. Pass a custom ``Agent`` subclass
                to give the group its own behavior.
            meta_attributes: Attributes to set on the group. When a group is
                reused, these are set on the existing group.
            meta_methods: Methods to bind to the group. When a group is
                reused, these are bound to the existing group.
            relation: Membership relation label for ``agents`` (default
                ``"member"``). Ignored when ``memberships`` is given.
            memberships: Alternative to ``agents``; a list of
                ``(member, relation)`` tuples so each member can get its own
                relation label. When given, ``agents`` and ``relation`` are
                ignored.

        Returns:
            The group agent (newly created or existing).

        Examples:
            Create a new team with two members (the group agent defaults to a
            plain ``Agent`` subclass):

            >>> team = model.meta_agents.create("Team", [alice, bob])

            Add carol to the same team. Reuse requires at least one given
            agent to already be in the group, so include an existing member:

            >>> team2 = model.meta_agents.create("Team", [carol, alice])
            >>> assert team is team2

            This is the same as adding carol using ``add_member`` (more
            explicit):

            >>> model.meta_agents.add_member("Team", carol)
            >>> assert carol in model.meta_agents.members_of("Team")

            With the same class name but no overlapping members, a second,
            distinct group is created:

            >>> other_team = model.meta_agents.create("Team", [dave])
            >>> assert other_team is not team

            Force new groups by using unique names:

            >>> team_a = model.meta_agents.create("Team_2026_A", [...])
            >>> team_b = model.meta_agents.create("Team_2026_B", [...])
        """
        agents, member_relations = _member_relations(agents, relation, memberships)
        meta_agent = _create_meta_agent_instance(
            self.model,
            new_agent_class,
            agents,
            modelly_agent_type,
            meta_attributes=meta_attributes,
            meta_methods=meta_methods,
            _membership_api=self,
        )
        self.backend.bulk_add(
            [(member, meta_agent, rel) for member, rel in member_relations]
        )
        return meta_agent

    def add_member(
        self,
        group: Hashable,
        member: Hashable,
        relation: RelationKey = "member",
    ) -> MembershipView:
        """Add one member to one group."""
        if member not in self.model.agents:  # use internal attribute for optimization
            raise ValueError(f"member {member!r} is not registered in the model")

        group = self._resolve_group(group)

        self.backend.add_membership(member, group, relation)
        return self.query_memberships(member)

    def remove_member(
        self,
        group: Hashable,
        member: Hashable,
        relation: RelationKey = "member",
    ) -> MembershipView:
        """Remove one member from one group."""
        group = self._resolve_group(group)

        self.backend.remove_membership(member, group, relation)
        return self.query_memberships(member)

    def dissolve(self, entity: Hashable) -> MembershipView:
        """Remove an entity's memberships and delete it from the model when possible."""
        snapshot = self._detach_entity(entity)
        if hasattr(entity, "_remove_from_model"):
            entity._remove_from_model()
        elif hasattr(entity, "remove"):
            entity.remove()
        return snapshot

    def deactivate(self, entity: Hashable) -> MembershipView:
        """Remove an entity from all memberships without deleting the object."""
        return self._detach_entity(entity)

    # TODO(perf): Add a cache_build staticmethod so models that constantly
    # reference the same sets of meta-agents can cache them instead of
    # constantly rebuilding the lookup. More involved, so a future iteration.
    evaluate_combination = staticmethod(evaluate_combination)
    find_combinations = staticmethod(find_combinations)


__all__ = [
    "MembershipEdge",
    "MembershipView",
    "MetaAgents",
]
