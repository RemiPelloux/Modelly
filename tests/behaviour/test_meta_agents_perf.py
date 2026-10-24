"""Tests for bulk membership removal and cached combination scoring."""

import random

import pytest

from modelly import Agent, Model
from modelly.behaviour.meta_agents import CachedEvaluation, MetaAgents
from modelly.behaviour.meta_agents.backend import MembershipBackend
from modelly.behaviour.meta_agents.meta_agent import MetaAgent

N_ENTITIES = 40
N_EDGES = 400
RELATIONS = ("member", "leader", "guest")
SEED = 42


class _PerEdgeBackend(MembershipBackend):
    """Reference backend using the original one-edge-at-a-time removal."""

    def remove_agent(self, agent):
        for group, relation in list(self._by_agent.get(agent, set())):
            self.remove_membership(agent, group, relation)

    def remove_group(self, group):
        for agent, relation in list(self._by_group.get(group, set())):
            self.remove_membership(agent, group, relation)


def _random_triplets(rng):
    """Random edges over one shared id space, so self-loops and cycles occur."""
    return [
        (
            rng.randrange(N_ENTITIES),
            rng.randrange(N_ENTITIES),
            rng.choice(RELATIONS),
        )
        for _ in range(N_EDGES)
    ]


def _snapshot(backend):
    """Return the triplets and both indexes as comparable plain values."""
    return (
        backend.as_triplets(),
        {key: set(value) for key, value in backend._by_agent.items()},
        {key: set(value) for key, value in backend._by_group.items()},
    )


@pytest.mark.parametrize("seed", range(5))
def test_bulk_removal_matches_per_edge_removal(seed):
    """Bulk removal leaves exactly the state per-edge removal leaves."""
    rng = random.Random(seed)
    triplets = _random_triplets(rng)
    fast, reference = MembershipBackend(), _PerEdgeBackend()
    fast.bulk_add(triplets)
    reference.bulk_add(triplets)
    for entity in rng.sample(range(N_ENTITIES), N_ENTITIES // 2):
        method = rng.choice(("remove_agent", "remove_group"))
        getattr(fast, method)(entity)
        getattr(reference, method)(entity)
        fast.assert_invariants()
        assert _snapshot(fast) == _snapshot(reference)


def test_removal_of_unknown_entity_is_a_no_op():
    """Removing an entity with no edges neither fails nor creates index keys."""
    backend = MembershipBackend()
    backend.add_membership("a", "g", "member")
    backend.remove_agent("missing")
    backend.remove_group("missing")
    assert "missing" not in backend._by_agent
    assert "missing" not in backend._by_group
    assert backend.as_triplets() == {("a", "g", "member")}


def test_removal_drops_emptied_index_keys():
    """Self-loops and last memberships leave no empty buckets behind."""
    backend = MembershipBackend()
    backend.bulk_add([("a", "a", "member"), ("a", "g", "member"), ("b", "g", "x")])
    backend.remove_agent("a")
    assert backend.as_triplets() == {("b", "g", "x")}
    assert set(backend._by_agent) == {"b"}
    assert set(backend._by_group) == {"g"}
    backend.remove_group("g")
    assert not backend.as_triplets()
    assert not backend._by_agent
    assert not backend._by_group


def test_triplets_of_matches_a_full_scan():
    """The indexed lookup returns what a scan over every triplet returns."""
    backend = MembershipBackend()
    backend.bulk_add(_random_triplets(random.Random(SEED)))
    for entity in range(N_ENTITIES):
        scanned = {t for t in backend.as_triplets() if entity in (t[0], t[1])}
        assert backend.triplets_of(entity) == scanned


def _run_model(seed):
    """Build random memberships, remove random agents, return id-level state."""
    model = Model(rng=seed)
    meta_agents = MetaAgents(model)
    agents = [Agent(model) for _ in range(N_ENTITIES)]
    groups = [meta_agents.create(f"G{i}", [agents[i]]) for i in range(len(RELATIONS))]
    for agent in agents:
        for group in model.random.sample(groups, 2):
            meta_agents.add_member(group, agent, model.random.choice(RELATIONS))
    for agent in model.random.sample(agents, N_ENTITIES // 2):
        agent.remove()
    meta_agents.backend.assert_invariants()
    views = [
        [(e.agent.unique_id, e.group.unique_id, e.relation) for e in view]
        for view in map(meta_agents.query_memberships, model.agents)
    ]
    triplets = {
        (a.unique_id, g.unique_id, r) for a, g, r in meta_agents.backend.as_triplets()
    }
    return triplets, views


def test_agent_removal_is_deterministic_for_a_seed():
    """Same seed, same memberships and the same ordered views after removals."""
    assert _run_model(SEED) == _run_model(SEED)


def test_removed_agent_leaves_no_memberships():
    """A removed agent disappears from every group and every view."""
    model = Model(rng=SEED)
    meta_agents = MetaAgents(model)
    alice, bob, carol = Agent(model), Agent(model), Agent(model)
    team = meta_agents.create("Team", [alice, bob])
    club = meta_agents.create("Club", [alice, carol])
    alice.remove()
    assert alice not in meta_agents.members_of(team)
    assert alice not in meta_agents.members_of(club)
    assert len(meta_agents.query_memberships(alice)) == 0
    assert meta_agents.query_memberships(team).agents == {bob}


def test_create_returns_a_meta_agent():
    """The creation path returns a MetaAgent, new or reused."""
    model = Model()
    meta_agents = MetaAgents(model)
    alice, bob = Agent(model), Agent(model)
    team = meta_agents.create("Team", [alice])
    assert isinstance(team, MetaAgent)
    assert meta_agents.create("Team", [alice, bob]) is team


def _score(group):
    """Deterministic score that depends on member order."""
    return sum(index * agent.unique_id for index, agent in enumerate(group, start=1))


def test_cache_build_keeps_find_combinations_results():
    """Cached scoring returns the same combinations, in the same order."""
    model = Model(rng=SEED)
    agents = [Agent(model) for _ in range(N_ENTITIES // 4)]
    cached = MetaAgents.cache_build(_score)
    expected = MetaAgents.find_combinations(agents, evaluation_func=_score)
    first = MetaAgents.find_combinations(agents, evaluation_func=cached)
    second = MetaAgents.find_combinations(agents, evaluation_func=cached)
    assert first == expected
    assert second == expected
    assert cached.misses == len(expected)
    assert cached.hits == len(expected)


def test_cache_build_calls_the_function_once_per_group():
    """Repeated searches only score unseen groups."""
    calls = []
    model = Model()
    agents = [Agent(model) for _ in range(len(RELATIONS) + 1)]
    meta_agents = MetaAgents(model)
    cached = meta_agents.cache_build(lambda group: calls.append(group) or len(group))
    for _ in range(len(RELATIONS)):
        meta_agents.find_combinations(agents, size=2, evaluation_func=cached)
    assert len(calls) == len(set(calls)) == len(cached)


def test_cache_invalidate_drops_only_matching_groups():
    """Invalidating an agent drops its groups; no arguments drops everything."""
    model = Model()
    alice, bob, carol = Agent(model), Agent(model), Agent(model)
    cached = MetaAgents.cache_build(_score)
    MetaAgents.find_combinations([alice, bob, carol], size=2, evaluation_func=cached)
    assert cached.invalidate(alice) == 2
    assert len(cached) == 1
    assert cached.invalidate() == 1
    assert len(cached) == 0


def test_cache_maxsize_evicts_oldest_first():
    """A bounded cache evicts in insertion order."""
    cached = MetaAgents.cache_build(len, maxsize=2)
    for group in [("a",), ("b",), ("c",)]:
        cached(group)
    assert len(cached) == 2
    cached(("a",))
    assert cached.misses == 4
    assert isinstance(cached, CachedEvaluation)


def test_cache_build_rejects_bad_arguments():
    """A non-callable function or a non-positive maxsize is rejected."""
    with pytest.raises(TypeError):
        MetaAgents.cache_build(None)
    with pytest.raises(ValueError):
        MetaAgents.cache_build(len, maxsize=0)
