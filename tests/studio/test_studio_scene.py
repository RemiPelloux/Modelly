"""The Map tab's scene: agents, network edges and region outlines as flat arrays, at scale."""

import base64
import time

import numpy as np
import pytest

from modelly import Model
from modelly.space.cells.agents import CellAgent
from modelly.space.continuous.agents import ContinuousSpaceAgent
from modelly.space.continuous.space import ContinuousSpace
from modelly.space.network import Network
from modelly.studio.scene import (
    MATPLOTLIB_LIMIT,
    element_count,
    encode,
    portrayal_colours,
    scene_of,
)
from modelly.viz.render.portrayal import AgentPortrayalStyle

nx = pytest.importorskip("networkx")

LARGE = 100_000
# Generous: building a 100k-element scene takes well under a second on a laptop.
SCENE_BUDGET_S = 5.0
SIDE = 1000.0
OFFSET = 600_000.0  # projected metres, as a GeoSpace would hold them


class Crowd(Model):
    """``n`` agents at random points of a continuous space far from the origin."""

    def __init__(self, n: int = 10, rng=1):  # noqa: D107
        super().__init__(rng=rng)
        bounds = [[OFFSET, OFFSET + SIDE], [OFFSET, OFFSET + SIDE]]
        self.space = ContinuousSpace(bounds, random=self.random, n_agents=n)
        for _ in range(n):
            agent = ContinuousSpaceAgent(self.space, self)
            agent.position = OFFSET + self.rng.random(2) * SIDE


class Graph(Model):
    """A random 4-regular network with one agent on every other node."""

    def __init__(self, nodes: int = 20, rng=1):  # noqa: D107
        super().__init__(rng=rng)
        self.grid = Network(
            nx.random_regular_graph(4, nodes, seed=1), random=self.random
        )
        for cell in list(self.grid.all_cells)[::2]:
            CellAgent(self).cell = cell


def decoded(text: str, dtype) -> np.ndarray:
    """The array a base64 buffer of ``encode`` holds."""
    return np.frombuffer(base64.b64decode(text), dtype=dtype)


def test_a_continuous_space_at_scale():
    """100 000 agents: one point each, shifted to the origin, built fast."""
    model = Crowd(LARGE)
    started = time.perf_counter()
    scene = scene_of(model)
    assert time.perf_counter() - started < SCENE_BUDGET_S
    assert scene.points.shape == (LARGE, 2)
    assert scene.points.dtype == np.float32
    assert scene.points.min() >= 0.0
    assert max(scene.extent) <= SIDE
    assert scene.origin[0] >= OFFSET
    assert element_count(model) > MATPLOTLIB_LIMIT


def test_a_network_at_scale():
    """A 50 000-node network: its nodes, its 100 000 edges and the agents on them."""
    model = Graph(LARGE // 2)
    started = time.perf_counter()
    scene = scene_of(model)
    assert time.perf_counter() - started < SCENE_BUDGET_S
    assert scene.nodes.shape == (LARGE // 2, 2)
    assert scene.segments.shape == (LARGE, 4)
    assert len(scene.points) == LARGE // 4
    assert element_count(model) == LARGE // 4 + LARGE


def test_grids_classes_and_encoding():
    """Grid agents stand at their cells; one class index per agent; buffers decode."""
    from modelly.examples import WolfSheep  # noqa: PLC0415

    model = WolfSheep()
    scene = scene_of(model)
    names = [name for name, _ in scene.legend]
    assert names == sorted(names) == ["GrassPatch", "Sheep", "Wolf"]
    assert len(scene.points) == len(model.agents)
    payload = encode(scene)
    assert payload["counts"] == [len(model.agents), 0, 0]
    np.testing.assert_array_equal(
        decoded(payload["points"], "<f4"), scene.points.ravel()
    )
    assert set(decoded(payload["classes"], "u1")) == {0, 1, 2}
    assert payload["colours"] == ""


def test_portrayal_colours():
    """A portrayal's colour per agent; an agent it returns None for is transparent."""
    model = Crowd(3)
    agents = list(model.space.active_agents)

    def portrayal(agent):
        return None if agent is agents[0] else AgentPortrayalStyle(color="#ff0000")

    colours = portrayal_colours(agents, portrayal)
    assert colours.tolist()[1] == [255, 0, 0, 255]
    assert colours[0, 3] == 0
    scene = scene_of(model, portrayal)
    assert scene.colours.shape == (3, 4)


def test_region_outlines_of_a_geospace():
    """A GeoSpace's region polygons become line segments around them."""
    gpd = pytest.importorskip("geopandas")
    shapely = pytest.importorskip("shapely")
    from modelly.space.geo import GeoAgent, GeoSpace  # noqa: PLC0415

    boxes = [shapely.box(0, 0, 100, 100), shapely.box(100, 0, 200, 100)]
    regions = gpd.GeoDataFrame({"name": ["a", "b"]}, geometry=boxes, crs="EPSG:32631")
    model = Model(rng=1)
    model.space = GeoSpace(regions, random=model.random)
    GeoAgent(model.space, model, (50.0, 50.0))
    scene = scene_of(model)
    assert scene.segments.shape == (8, 4)  # four sides per square
    assert scene.points.tolist() == [[50.0, 50.0]]


def test_no_space():
    """A model without a space has no scene."""
    assert scene_of(Model(rng=1)) is None
