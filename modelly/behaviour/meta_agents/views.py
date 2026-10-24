"""Read-only membership snapshots returned by the membership manager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modelly.behaviour.meta_agents.backend import RelationKey


@dataclass(frozen=True, slots=True)
class MembershipEdge:
    """A membership edge with live agent and group objects."""

    agent: Any
    group: Any
    relation: RelationKey


@dataclass(frozen=True, slots=True)
class MembershipView:
    """Read-only snapshot of memberships for one entity."""

    subject: Any
    memberships: tuple[MembershipEdge, ...]

    def __iter__(self):
        """Iterate over the resolved memberships."""
        return iter(self.memberships)

    def __len__(self) -> int:
        """Return the number of resolved memberships."""
        return len(self.memberships)

    def as_triplets(self) -> set[tuple[Any, Any, RelationKey]]:
        """Return the memberships as live-object triplets."""
        return {(edge.agent, edge.group, edge.relation) for edge in self.memberships}

    @property
    def agents(self) -> set[Any]:
        """Return all unique agents referenced by the view."""
        return {edge.agent for edge in self.memberships}

    @property
    def groups(self) -> set[Any]:
        """Return all unique groups referenced by the view."""
        return {edge.group for edge in self.memberships}

    @property
    def relations(self) -> set[RelationKey]:
        """Return all unique relation labels referenced by the view."""
        return {edge.relation for edge in self.memberships}
