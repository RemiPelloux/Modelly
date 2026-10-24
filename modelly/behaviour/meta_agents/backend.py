"""Storage for overlapping meta-agent memberships.

- Membership edges (agent, group, relation)
- Safe update operations
- Invariant checks
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable, Iterable

RelationKey = Hashable
Triplet = tuple[Hashable, Hashable, RelationKey]


def _discard_from_index(
    index: dict[Hashable, set[tuple[Hashable, RelationKey]]],
    entries: Iterable[tuple[Hashable, tuple[Hashable, RelationKey]]],
) -> None:
    """Discard ``(key, entry)`` pairs from an index, dropping emptied keys."""
    for key, entry in entries:
        bucket = index.get(key)
        if bucket is None:
            continue
        bucket.discard(entry)
        if not bucket:
            del index[key]


class MembershipBackend:
    """Store of overlapping memberships."""

    def __init__(self) -> None:
        """Initialize empty triplet storage and bidirectional indexes."""
        self._triplets: set[Triplet] = set()
        self._by_agent: dict[Hashable, set[tuple[Hashable, RelationKey]]] = defaultdict(
            set
        )
        self._by_group: dict[Hashable, set[tuple[Hashable, RelationKey]]] = defaultdict(
            set
        )

    def add_membership(
        self, agent: Hashable, group: Hashable, relation: RelationKey
    ) -> None:
        """Add one membership edge if it does not already exist."""
        triplet = (agent, group, relation)
        if triplet in self._triplets:
            return
        self._triplets.add(triplet)
        self._by_agent[agent].add((group, relation))
        self._by_group[group].add((agent, relation))

    def bulk_add(self, memberships: Iterable[Triplet]) -> None:
        """Add many membership edges."""
        for agent, group, relation in memberships:
            self.add_membership(agent, group, relation)

    def remove_membership(
        self, agent: Hashable, group: Hashable, relation: RelationKey
    ) -> None:
        """Remove one membership edge if present."""
        triplet = (agent, group, relation)
        if triplet not in self._triplets:
            return
        self._triplets.remove(triplet)

        self._by_agent[agent].discard((group, relation))
        if not self._by_agent[agent]:
            del self._by_agent[agent]

        self._by_group[group].discard((agent, relation))
        if not self._by_group[group]:
            del self._by_group[group]

    def replace_relation(
        self,
        agent: Hashable,
        group: Hashable,
        old_relation: RelationKey,
        new_relation: RelationKey,
    ) -> None:
        """Replace one relation label for one agent-group pair."""
        self.remove_membership(agent, group, old_relation)
        self.add_membership(agent, group, new_relation)

    def remove_agent(self, agent: Hashable) -> None:
        """Remove an agent and all incident memberships."""
        # One index pop, then one reverse-index update per incident group.
        edges = self._by_agent.pop(agent, None)
        if not edges:
            return
        self._triplets.difference_update(
            (agent, group, relation) for group, relation in edges
        )
        _discard_from_index(self._by_group, ((g, (agent, r)) for g, r in edges))

    def remove_group(self, group: Hashable) -> None:
        """Remove a group and all incident memberships."""
        # Mirror of remove_agent with the two indexes swapped.
        edges = self._by_group.pop(group, None)
        if not edges:
            return
        self._triplets.difference_update(
            (agent, group, relation) for agent, relation in edges
        )
        _discard_from_index(self._by_agent, ((a, (group, r)) for a, r in edges))

    def groups_of(
        self, agent: Hashable, relation: RelationKey | None = None
    ) -> set[Hashable]:
        """Return groups for an agent, optionally filtered by relation."""
        entries = self._by_agent.get(agent, set())
        if relation is None:
            return {group for group, _ in entries}
        return {group for group, rel in entries if rel == relation}

    def agents_of(
        self, group: Hashable, relation: RelationKey | None = None
    ) -> set[Hashable]:
        """Return agents for a group, optionally filtered relation."""
        entries = self._by_group.get(group, set())
        if relation is None:
            return {agent for agent, _ in entries}
        return {agent for agent, rel in entries if rel == relation}

    def relations_between(self, agent: Hashable, group: Hashable) -> set[RelationKey]:
        """Return all relation types between one agent and one group."""
        return {
            relation
            for linked_group, relation in self._by_agent.get(agent, set())
            if linked_group == group
        }

    def triplets_of(self, entity: Hashable) -> set[Triplet]:
        """Return the memberships where ``entity`` is the agent or the group."""
        triplets = {
            (entity, group, relation)
            for group, relation in self._by_agent.get(entity, ())
        }
        triplets.update(
            (agent, entity, relation)
            for agent, relation in self._by_group.get(entity, ())
        )
        return triplets

    def as_triplets(self) -> set[Triplet]:
        """Return all memberships as canonical triplets."""
        return set(self._triplets)

    def assert_invariants(self) -> None:
        """Assert internal consistency between triplets and indexes."""
        # Triplets must match both indexes.
        for agent, group, relation in self._triplets:
            assert (group, relation) in self._by_agent.get(agent, set())
            assert (agent, relation) in self._by_group.get(group, set())

        # Agent index must match triplets
        for agent, edges in self._by_agent.items():
            for group, relation in edges:
                assert (agent, group, relation) in self._triplets

        # Group index must match triplets
        for group, edges in self._by_group.items():
            for agent, relation in edges:
                assert (agent, group, relation) in self._triplets
