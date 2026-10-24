"""Read side of the membership manager: name resolution and membership queries."""

from __future__ import annotations

from collections import deque
from collections.abc import Hashable, Iterable
from typing import TYPE_CHECKING, Any

from modelly.behaviour.meta_agents.views import MembershipEdge, MembershipView
from modelly.core.agent import AgentSet

if TYPE_CHECKING:
    from modelly.behaviour.meta_agents.backend import (
        MembershipBackend,
        RelationKey,
        Triplet,
    )


class MembershipQueries:
    """Group resolution and read-only membership queries for MetaAgents."""

    if TYPE_CHECKING:
        # Set by MetaAgents.__init__.
        model: Any
        backend: MembershipBackend

    def _resolve_group(self, group: Hashable) -> Any:
        """Resolve a group from a live object or group name."""
        if group in self.model.agents:
            return group
        # Try string name resolution.
        if isinstance(group, str):
            matches = list(
                dict.fromkeys(
                    entity
                    for entity in self.model.agents
                    if getattr(entity, "name", None) == group
                    or entity.__class__.__name__ == group
                )
            )
            if len(matches) == 1:
                return matches[0]
            if not matches:
                raise ValueError(f"No group named {group!r}")
            raise ValueError(f"Ambiguous group name {group!r}")
        return group

    def _resolve_view(self, entity: Any, triplets: Iterable[Triplet]) -> MembershipView:
        """Convert backend triplets into a user-facing snapshot."""
        resolved_edges: list[MembershipEdge] = []
        for agent, group, relation in sorted(
            triplets,
            key=lambda triplet: (
                str(triplet[0]),
                str(triplet[1]),
                repr(triplet[2]),
            ),
        ):
            resolved_edges.append(
                MembershipEdge(
                    agent=agent,
                    group=group,
                    relation=relation,
                )
            )

        return MembershipView(
            subject=entity,
            memberships=tuple(resolved_edges),
        )

    def members_of(
        self, group: Hashable, relation: RelationKey | None = None
    ) -> AgentSet:
        """Return the live members of one group as an AgentSet."""
        group = self._resolve_group(group)
        members = sorted(self.backend.agents_of(group, relation=relation), key=str)
        return AgentSet(members, random=self.model.random)

    def groups_of(
        self, agent: Hashable, relation: RelationKey | None = None
    ) -> AgentSet:
        """Return the live groups that contain one agent as an AgentSet."""
        groups = sorted(self.backend.groups_of(agent, relation=relation), key=str)
        return AgentSet(groups, random=self.model.random)

    def query_memberships(
        self, entity: Hashable, relation: RelationKey | None = None
    ) -> MembershipView:
        """Return a resolved, read-only snapshot of one entity's memberships."""
        triplets = (
            triplet
            for triplet in self.backend.triplets_of(entity)
            if relation is None or triplet[2] == relation
        )
        return self._resolve_view(entity, triplets)

    def at_level(
        self,
        level: int,
        *,
        root: Hashable,
        relation: RelationKey | None = "member",
    ) -> AgentSet:
        """Return agents at a containment depth below ``root``.

        Levels are structural shortest-path distances through membership edges,
        not a persistent ``agent.level`` property. ``root`` is level ``0``; its
        direct members are level ``1``. When an agent is reachable by more than
        one path, it appears only at its shallowest depth from ``root``.

        Parameters
        ----------
        level : int
            Non-negative containment depth relative to ``root``.
        root : Hashable
            Hierarchy root (live agent or unique id). Must be registered on
            this model's membership manager.
        relation : RelationKey or None, default ``"member"``
            Membership relation to traverse. ``None`` includes all relations.

        Returns:
        -------
        AgentSet
            Live agents at the requested level (empty if none).

        Raises:
        ------
        ValueError
            If ``level`` is negative or ``root`` is not in the model.

        Examples:
        --------
        >>> model.meta_agents.at_level(4, root=world)
        """
        if level < 0:
            raise ValueError(f"level must be non-negative, got {level}")

        if root not in self.model.agents:
            raise ValueError(f"root {root!r} is not registered in the model")

        if level == 0:
            return AgentSet([root], random=self.model.random)
        return AgentSet(
            self._members_at_depth(root, level, relation), random=self.model.random
        )

    def _members_at_depth(
        self, root: Hashable, level: int, relation: RelationKey | None
    ) -> list[Any]:
        """Breadth-first search for the members first reached at ``level``."""
        # BFS downward: group -> members. First visit is nearest depth.
        visited: set[Hashable] = {root}
        queue: deque[tuple[Hashable, int]] = deque([(root, 0)])
        at_depth: list[Any] = []

        while queue:
            group, depth = queue.popleft()
            if depth >= level:
                continue
            members = sorted(
                self.backend.agents_of(group, relation=relation),
                key=str,
            )
            for member in members:
                if member in visited:
                    continue
                visited.add(member)
                next_depth = depth + 1
                if next_depth == level:
                    at_depth.append(member)
                elif next_depth < level:
                    queue.append((member, next_depth))

        return at_depth
