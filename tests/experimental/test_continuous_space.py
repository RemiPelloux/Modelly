"""Tests for continuous space."""

import numpy as np
import pytest

from modelly import Model
from modelly.agent import AgentSet
from modelly.experimental.continuous_space import ContinuousSpace, ContinuousSpaceAgent


def test_continuous_space():
    """Test ContinuousSpace class."""
    model = Model(rng=42)

    dimensions = np.asarray([[0, 1], [-1, 0]])
    space = ContinuousSpace(dimensions, torus=False, random=model.random)

    # check some default fields
    assert space.ndims == 2
    assert np.all(space.size == [1, 1])
    assert np.all(space.center == [0.5, -0.5])
    assert len(space.agents) == 0

    # check in_bounds
    assert space.in_bounds([0.5, -0.5])
    assert not space.in_bounds([-0.5, -0.5])
    assert not space.in_bounds([1.5, -0.5])
    assert not space.in_bounds([0.5, 0.5])
    assert not space.in_bounds([0.5, -1.5])

    # check torus correction
    space = ContinuousSpace(dimensions, torus=True, random=model.random)
    assert np.all(space.torus_correct([-0.5, 0.5]) == [0.5, -0.5])
    assert np.all(space.torus_correct([0.5, -0.5]) == [0.5, -0.5])
    assert np.all(space.torus_correct([0.5, -0.5]) == [0.5, -0.5])
    assert np.all(space.torus_correct([1.5, -0.5]) == [0.5, -0.5])
    assert np.all(space.torus_correct([0.5, -1.5]) == [0.5, -0.5])

    # check 3d
    dimensions = np.asarray([[0, 2], [-2, 0], [-2, 2]])
    space = ContinuousSpace(dimensions, torus=False, random=model.random)

    # check some default fields
    assert space.ndims == 3
    assert np.all(space.size == [2, 2, 4])
    assert np.all(space.center == [1, -1, 0])

    # check in_bounds
    assert space.in_bounds([1, -1, 0])
    assert not space.in_bounds([-0.5, -1, 0])
    assert not space.in_bounds([2.5, -1, 0])
    assert not space.in_bounds([1, 0.5, 0])
    assert not space.in_bounds([1, -2.5, 0])
    assert not space.in_bounds([1, -1, -3])
    assert not space.in_bounds([1, -1, 3])
    assert not space.in_bounds([-0.5, -1, 3])
    assert not space.in_bounds([1, 0.5, 3])


def test_continuous_agent():
    """Test ContinuousSpaceAgent class."""
    model = Model(rng=42)

    dimensions = np.asarray([[0, 1], [0, 1]])
    space = ContinuousSpace(dimensions, torus=False, random=model.random)

    for _ in range(10):
        agent = ContinuousSpaceAgent(space, model)
        position = [agent.random.random(), agent.random.random()]
        agent.position = position
        agent.coordinate = position

    assert space.agent_positions.shape == (10, 2)
    for agent in space.agents:
        a = agent.position
        b = space._agent_positions[agent._modelly_index]
        assert np.all(a == b)
        assert np.all(agent.position == agent.coordinate)

    # add more agents, triggering a resizeing of the array
    for _ in range(100):
        agent = ContinuousSpaceAgent(space, model)
        position = [agent.random.random(), agent.random.random()]
        agent.position = position
        agent.coordinate = position

    assert space.agent_positions.shape == (110, 2)
    for agent in space.agents:
        a = agent.position
        b = space._agent_positions[agent._modelly_index]
        assert np.all(a == b)
        assert np.all(agent.position == agent.coordinate)

    # remove all agents and check if the view is updated throughout correctly
    for i, agent in enumerate(space.agents):
        assert np.all(
            agent.position == agent.coordinate
        )  ## check if updates of indices is correctly done
        agent.remove()
        assert space.agent_positions.shape == (110 - 1 - i, 2)

    model = Model(rng=42)

    dimensions = np.asarray([[0, 1], [0, 1]])
    space = ContinuousSpace(dimensions, torus=True, random=model.random)
    agent = ContinuousSpaceAgent(space, model)
    agent.position = [1.1, 1.1]
    assert np.allclose(agent.position, [0.1, 0.1])

    dimensions = np.asarray([[0, 1], [0, 1]])
    space = ContinuousSpace(dimensions, torus=False, random=model.random)
    agent = ContinuousSpaceAgent(space, model)
    with pytest.raises(ValueError):
        agent.position = [1.1, 1.1]


def test_continous_space_calculate_distances():
    """Test ContinuousSpace.distance method."""
    # non torus
    model = Model(rng=42)
    dimensions = np.asarray([[0, 1], [0, 1]])
    space = ContinuousSpace(dimensions, torus=False, random=model.random)

    agent = ContinuousSpaceAgent(space, model)
    agent.position = [0.1, 0.1]

    distances, agents = space.calculate_distances([0.1, 0.9])
    assert np.all(
        distances
        == [
            0.8,
        ]
    )
    assert np.all(
        agents
        == [
            agent,
        ]
    )

    distances, agents = space.calculate_distances([0.9, 0.1])
    assert np.all(
        distances
        == [
            0.8,
        ]
    )
    assert np.all(
        agents
        == [
            agent,
        ]
    )

    # torus
    model = Model(rng=42)
    dimensions = np.asarray([[0, 1], [0, 1]])
    space = ContinuousSpace(dimensions, torus=True, random=model.random)

    agent = ContinuousSpaceAgent(space, model)
    agent.position = [0.1, 0.1]

    distances, agents = space.calculate_distances([0.1, 0.9])
    assert np.all(
        np.isclose(
            distances,
            [
                0.2,
            ],
        )
    )
    assert np.all(
        agents
        == [
            agent,
        ]
    )

    distances, agents = space.calculate_distances([0.9, 0.1])
    assert np.all(
        np.isclose(
            distances,
            [
                0.2,
            ],
        )
    )
    assert np.all(
        agents
        == [
            agent,
        ]
    )

    distances, agents = space.calculate_distances([0.9, 0.9])
    assert np.all(
        np.isclose(
            distances,
            [
                0.2 * 2**0.5,
            ],
        )
    )
    assert np.all(
        agents
        == [
            agent,
        ]
    )

    distances, agents = space.calculate_distances(
        [0.9, 0.9],
        agents=[
            agent,
        ],
    )
    assert np.all(
        np.isclose(
            distances,
            [
                0.2 * 2**0.5,
            ],
        )
    )
    assert np.all(
        agents
        == [
            agent,
        ]
    )


def test_continous_space_difference_vector():
    """Test ContinuousSpace.get_difference_vector method."""
    # non torus
    model = Model(rng=42)
    dimensions = np.asarray([[0, 1], [0, 1]])
    space = ContinuousSpace(dimensions, torus=False, random=model.random)

    agent = ContinuousSpaceAgent(space, model)
    agent.position = [0.1, 0.1]

    vector = space.calculate_difference_vector([0.1, 0.9])
    assert np.all(vector == [0, -0.8])

    vector = space.calculate_difference_vector([0.9, 0.1])
    assert np.all(vector == [-0.8, 0])

    # torus
    model = Model(rng=42)
    dimensions = np.asarray([[0, 1], [0, 1]])
    space = ContinuousSpace(dimensions, torus=True, random=model.random)

    agent = ContinuousSpaceAgent(space, model)
    agent.position = [0.1, 0.1]

    vector = space.calculate_difference_vector([0.1, 0.9])
    assert np.allclose(vector, [0, 0.2])

    vector = space.calculate_difference_vector([0.9, 0.1])
    assert np.allclose(vector, [0.2, 0])

    vector = space.calculate_difference_vector([0.9, 0.9])
    assert np.allclose(vector, [0.2, 0.2])


def test_continuous_space_get_k_nearest_agents():  # noqa: D103
    # non torus
    model = Model(rng=42)
    dimensions = np.asarray([[0, 1], [0, 1]])
    space = ContinuousSpace(dimensions, torus=False, random=model.random)

    agent = ContinuousSpaceAgent(space, model)
    agent.position = [0.1, 0.1]

    agent = ContinuousSpaceAgent(space, model)
    agent.position = [0.1, 0.9]

    agent = ContinuousSpaceAgent(space, model)
    agent.position = [0.9, 0.1]

    agent = ContinuousSpaceAgent(space, model)
    agent.position = [0.9, 0.9]

    agent = ContinuousSpaceAgent(space, model)
    agent.position = [0.5, 0.5]

    agents, distances = space.get_k_nearest_agents([0.1, 0.1], k=1)
    assert len(agents) == 1
    assert np.allclose(
        distances,
        [
            0,
        ],
    )

    agents, distances = space.get_k_nearest_agents([0.5, 0.1], k=1)
    assert len(agents) == 1
    assert np.allclose(distances, [0.4, 0.4])

    agents, distances = space.get_k_nearest_agents([0.5, 0.1], k=2)
    assert len(agents) == 2
    assert np.allclose(distances, [0.4, 0.4])

    # torus
    model = Model(rng=42)
    dimensions = np.asarray([[0, 1], [0, 1]])
    space = ContinuousSpace(dimensions, torus=True, random=model.random)

    agent = ContinuousSpaceAgent(space, model)
    agent.position = [0.1, 0.1]

    agent = ContinuousSpaceAgent(space, model)
    agent.position = [0.9, 0.1]

    agent = ContinuousSpaceAgent(space, model)
    agent.position = [0.9, 0.9]

    agents, distances = space.get_k_nearest_agents([0.0, 0.1], k=2)
    assert len(agents) == 2
    assert np.allclose(distances, [0.1, 0.1])


def test_continuous_space_get_agents_in_radius():  # noqa: D103
    # non torus
    model = Model(rng=42)
    dimensions = np.asarray([[0, 1], [0, 1]])
    space = ContinuousSpace(dimensions, torus=False, random=model.random)

    positions = [
        [0.1, 0.1],
        [0.1, 0.9],
        [0.9, 0.1],
        [0.9, 0.9],
        [0.5, 0.5],
    ]

    for position in positions:
        agent = ContinuousSpaceAgent(space, model)
        agent.position = position

    agents, distances = space.get_agents_in_radius([0.1, 0.1], radius=0.1)
    assert len(agents) == 1
    assert np.allclose(
        distances,
        [
            0,
        ],
    )

    agents, distances = space.get_agents_in_radius([0.5, 0.1], radius=0.4)
    assert len(agents) == 3
    assert np.allclose(distances, [0.4, 0.4, 0.4])

    agents, distances = space.get_agents_in_radius([0.5, 0.5], radius=1)
    assert len(agents) == 5

    # torus
    model = Model(rng=42)
    dimensions = np.asarray([[0, 1], [0, 1]])
    space = ContinuousSpace(dimensions, torus=True, random=model.random)

    positions = [
        [0.1, 0.1],
        [0.1, 0.9],
        [0.9, 0.1],
        [0.9, 0.9],
        [0.5, 0.5],
    ]

    for position in positions:
        agent = ContinuousSpaceAgent(space, model)
        agent.position = position

    agents, distances = space.get_agents_in_radius([0.0, 0.1], radius=0.1)
    assert len(agents) == 2
    assert np.allclose(distances, [0.1, 0.1])


def test_get_neighbor_methos():  # noqa: D103
    # non torus
    model = Model(rng=42)
    dimensions = np.asarray([[0, 1], [0, 1]])
    space = ContinuousSpace(dimensions, torus=False, random=model.random)

    positions = [
        [0.1, 0.1],
        [0.1, 0.9],
        [0.9, 0.1],
        [0.9, 0.9],
        [0.5, 0.5],
    ]

    for position in positions:
        agent = ContinuousSpaceAgent(space, model)
        agent.position = position

    agent: ContinuousSpaceAgent = model.agents[-1]  # 0.5, 0.5
    agents, distances = agent.get_neighbors_in_radius(1)
    assert len(agents) == 4

    agents, distances = agent.get_neighbors_in_radius(0.1)
    assert len(agents) == 0

    agent: ContinuousSpaceAgent = model.agents[0]  # 0.1, 0.1
    agents, distances = agent.get_nearest_neighbors(k=2)
    assert len(agents) == 2

    # torus
    model = Model(rng=42)
    dimensions = np.asarray([[0, 1], [0, 1]])
    space = ContinuousSpace(dimensions, torus=True, random=model.random)

    positions = [
        [0.1, 0.1],
        [0.1, 0.9],
        [0.9, 0.1],
        [0.9, 0.9],
        [0.5, 0.5],
    ]

    for position in positions:
        agent = ContinuousSpaceAgent(space, model)
        agent.position = position

    agent: ContinuousSpaceAgent = model.agents[-1]  # 0.5, 0.5
    agents, distances = agent.get_neighbors_in_radius(1)
    assert len(agents) == 4

    agent: ContinuousSpaceAgent = model.agents[0]  # 0.1, 0.1
    agents, distances = agent.get_nearest_neighbors(k=2)
    assert len(agents) == 2
    assert np.allclose(distances, [0.2, 0.2])


def test_agent_removal_no_ghost_entries():
    """Test that removing an agent doesn't leave ghost entries in _index_to_agent.

    This test verifies the fix for the "Ghost Agent" bug where removing an agent
    from ContinuousSpace would leave stale entries in the internal _index_to_agent
    dictionary. The bug occurred because when agents were shifted to fill the gap
    left by a removed agent, the old index entry of the last shifted agent was not
    deleted.

    Regression test for GitHub issue #3029.
    """
    model = Model(rng=42)
    dimensions = np.asarray([[0, 10], [0, 10]])

    # Test 1: Remove middle agent
    space = ContinuousSpace(dimensions, torus=False, random=model.random)
    agents = []
    for i in range(3):
        agent = ContinuousSpaceAgent(space, model)
        agent.position = [float(i), float(i)]
        agents.append(agent)

    space._remove_agent(agents[1])
    assert len(space.active_agents) == 2
    assert len(space._index_to_agent) == 2

    for idx, agent in enumerate(space.active_agents):
        assert agent._modelly_index == idx
        assert space._index_to_agent[idx] == agent

    # Test 2: Remove last agent
    space = ContinuousSpace(dimensions, torus=False, random=model.random)
    agents = [ContinuousSpaceAgent(space, model) for _ in range(3)]
    for i, agent in enumerate(agents):
        agent.position = [float(i), float(i)]

    space._remove_agent(agents[2])
    assert len(space.active_agents) == 2
    assert len(space._index_to_agent) == 2

    # Test 3: Sequential removals
    space = ContinuousSpace(dimensions, torus=False, random=model.random)
    agents = [ContinuousSpaceAgent(space, model) for _ in range(5)]
    for i, agent in enumerate(agents):
        agent.position = [float(i), float(i)]

    space._remove_agent(agents[2])
    assert len(space.active_agents) == 4
    assert len(space._index_to_agent) == 4

    space._remove_agent(agents[0])
    assert len(space.active_agents) == 3
    assert len(space._index_to_agent) == 3

    for idx, agent in enumerate(space.active_agents):
        assert agent._modelly_index == idx
        assert space._index_to_agent[idx] == agent


def test_continuous_space_k_larger_than_population():
    """Test that k larger than population returns all agents with a warning."""
    model = Model(rng=42)
    space = ContinuousSpace([[0, 10], [0, 10]], random=model.random)

    a1 = ContinuousSpaceAgent(space, model)
    a1.position = np.array([1.0, 1.0])

    a2 = ContinuousSpaceAgent(space, model)
    a2.position = np.array([9.0, 9.0])

    with pytest.warns(UserWarning, match="only 2 agent"):
        agents, dists = space.get_k_nearest_agents(np.array([5.0, 5.0]), k=10)

    assert len(agents) == 2
    assert len(dists) == 2


def test_continuous_space_k_empty_space():
    """Test that empty space returns no agents."""
    model = Model(rng=42)
    space = ContinuousSpace([[0, 10], [0, 10]], random=model.random)

    agents, dists = space.get_k_nearest_agents(np.array([5.0, 5.0]), k=1)

    assert agents == []
    assert len(dists) == 0


def test_continuous_space_k_zero():
    """Test that k=0 returns empty result."""
    model = Model(rng=42)
    space = ContinuousSpace([[0, 10], [0, 10]], random=model.random)

    a = ContinuousSpaceAgent(space, model)
    a.position = np.array([1.0, 1.0])

    agents, dists = space.get_k_nearest_agents(np.array([5.0, 5.0]), k=0)

    assert agents == []
    assert len(dists) == 0


def test_continuous_space_k_exact():
    """Test that exact k nearest agents are returned."""
    model = Model(rng=42)
    space = ContinuousSpace([[0, 10], [0, 10]], random=model.random)

    agents_list = [ContinuousSpaceAgent(space, model) for _ in range(3)]
    positions = [
        np.array([1.0, 1.0]),
        np.array([2.0, 2.0]),
        np.array([9.0, 9.0]),
    ]

    for agent, pos in zip(agents_list, positions):
        agent.position = pos

    agents, dists = space.get_k_nearest_agents(np.array([0.0, 0.0]), k=2)

    assert len(agents) == 2
    assert len(dists) == 2


def test_continuous_space_generics():
    """Test PEP 695 generic typing preservation in ContinuousSpace."""

    class CustomAgent(ContinuousSpaceAgent):
        pass

    model = Model(rng=42)
    dimensions = np.asarray([[0, 10], [0, 10]])
    space = ContinuousSpace[CustomAgent](dimensions, torus=False, random=model.random)

    agent = CustomAgent(space, model)
    agent.position = [1.0, 1.0]

    # Verify return types statically & dynamically
    agents: AgentSet[CustomAgent] = space.agents
    assert len(agents) == 1
    assert isinstance(agents.to_list()[0], CustomAgent)

    in_radius, _ = space.get_agents_in_radius([1.0, 1.0], radius=2.0)
    assert len(in_radius) == 1
    assert isinstance(in_radius[0], CustomAgent)

    k_nearest, _ = space.get_k_nearest_agents([1.0, 1.0], k=1)
    assert len(k_nearest) == 1
    assert isinstance(k_nearest[0], CustomAgent)


def test_neighbors_within_matches_per_agent_query():
    """The batched KD-tree query agrees with the per-agent scan, torus or not."""
    for torus in (False, True):
        model = Model(rng=42)
        space = ContinuousSpace([[0, 10], [0, 10]], torus=torus, random=model.random)
        agents = [ContinuousSpaceAgent(space, model) for _ in range(60)]
        for agent in agents:
            agent.position = model.rng.random(2) * 10
        lists = space.neighbors_within(2.5)
        assert set(lists) == set(agents)
        for agent in agents:
            expected, _ = agent.get_neighbors_in_radius(2.5)
            assert set(lists[agent]) == set(expected)
            assert agent not in lists[agent]


def test_neighbors_within_wraps_on_torus():
    """Two agents on opposite edges are neighbours only on a torus."""
    for torus, expected in ((True, 1), (False, 0)):
        model = Model(rng=1)
        space = ContinuousSpace([[0, 10], [0, 10]], torus=torus, random=model.random)
        a, b = ContinuousSpaceAgent(space, model), ContinuousSpaceAgent(space, model)
        a.position = np.array([0.2, 5.0])
        b.position = np.array([9.8, 5.0])
        assert len(space.neighbors_within(1.0)[a]) == expected


def test_neighbors_within_empty_space():
    """An empty space has no neighbour lists."""
    model = Model(rng=1)
    space = ContinuousSpace([[0, 10], [0, 10]], random=model.random)
    assert space.neighbors_within(1.0) == {}


def test_neighbors_within_is_cached_until_positions_change():
    """The same positions reuse the lists; a move or a new agent refreshes them."""
    model = Model(rng=1)
    space = ContinuousSpace([[0, 10], [0, 10]], random=model.random)
    agents = [ContinuousSpaceAgent(space, model) for _ in range(5)]
    for i, agent in enumerate(agents):
        agent.position = np.array([float(i), 0.0])
    first = space.neighbors_within(1.5)
    assert space.neighbors_within(1.5) is first
    assert space.neighbors_within(2.5) is not first
    agents[0].position = np.array([9.0, 9.0])
    moved = space.neighbors_within(1.5)
    assert moved is not first and moved[agents[0]] == []
    ContinuousSpaceAgent(space, model).position = np.array([9.0, 8.5])
    assert len(space.neighbors_within(1.5)[agents[0]]) == 1
