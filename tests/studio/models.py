"""Small importable models for the Studio tests (checkpoint copies import them by name)."""

from modelly import Model
from modelly.data.collector import DataCollector
from modelly.space.cells.agents import CellAgent
from modelly.space.continuous.agents import ContinuousSpaceAgent
from modelly.space.continuous.space import ContinuousSpace
from modelly.space.continuous.vectorised import move_all
from modelly.space.network import Network

START = 10.0
NOISE_SD = 0.5
SWARM_SIZE = 100_000
SWARM_SIDE = 1000.0
WEB_EDGES = 100_000
WEB_DEGREE = 4
GRAPH_SEED = 1


class Growth(Model):
    """A count that grows by ``rate`` per step, with noise; ``rate`` is a plain attribute."""

    def __init__(self, rate: float = 0.1, rng=None):  # noqa: D107
        super().__init__(rng=rng)
        self.rate = rate
        self.count = START
        self.datacollector = DataCollector({"count": "count"})
        self.datacollector.collect(self)

    def step(self):  # noqa: D102
        self.count += self.count * self.rate + self.rng.normal(0.0, NOISE_SD)
        self.datacollector.collect(self)


class Swarm(Model):
    """``n`` agents drifting in a continuous space: the map's scale test."""

    def __init__(self, n: int = SWARM_SIZE, rng=None):  # noqa: D107
        super().__init__(rng=rng)
        bounds = [[0.0, SWARM_SIDE], [0.0, SWARM_SIDE]]
        self.space = ContinuousSpace(bounds, torus=True, random=self.random, n_agents=n)
        positions = self.rng.random((n, 2)) * SWARM_SIDE
        for position in positions:
            ContinuousSpaceAgent(self.space, self).position = position

    def step(self):  # noqa: D102
        moves = self.rng.normal(0.0, 1.0, self.space.agent_positions.shape)
        move_all(self.space, self.space.agent_positions + moves)


class Web(Model):
    """A random network with ``edges`` edges and an agent on every other node."""

    def __init__(self, edges: int = WEB_EDGES, rng=None):  # noqa: D107
        super().__init__(rng=rng)
        import networkx as nx  # noqa: PLC0415 (the network extra)

        nodes = 2 * edges // WEB_DEGREE
        graph = nx.random_regular_graph(WEB_DEGREE, nodes, seed=GRAPH_SEED)
        self.grid = Network(graph, random=self.random)
        for cell in list(self.grid.all_cells)[::2]:
            CellAgent(self).cell = cell


class Silent(Model):
    """A model that collects nothing: no reporter for a band to read."""

    def __init__(self, size: int = 3, rng=None):  # noqa: D107
        super().__init__(rng=rng)
        self.size = size
