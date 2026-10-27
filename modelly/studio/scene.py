"""What the Map tab draws: agents as points, network edges and region outlines as lines.

``scene_of(model)`` reads the model's space into flat arrays a WebGL (or Canvas 2D) renderer
uploads as they are:

- ``points``: one ``(x, y)`` per agent: its position in a continuous or geographic space,
  else its cell's position (a network node's layout position, a grid cell's coordinate);
- ``classes``: each point's agent class, an index into ``legend`` (one Okabe-Ito colour per
  class, in name order);
- ``nodes``: a network's nodes, drawn small and grey under the agents;
- ``segments``: ``(x0, y0, x1, y1)`` per line: a network's edges, a ``GeoSpace``'s region
  outlines.

Coordinates are shifted so the scene's lower-left corner is the origin: projected metres
(six or seven digits) lose no precision in the renderer's 32-bit floats that way.
``encode`` packs the arrays as base64 little-endian buffers for the browser.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
from matplotlib.colors import to_rgba_array

from modelly.viz.mpl.figure import model_space
from modelly.viz.palettes import OKABE_ITO

if TYPE_CHECKING:
    from modelly.core.model import Model

XY = 2
SEGMENT = 4
FLOAT = "<f4"
CLASS_INDEX = "u1"
# More agent classes than this share the last colour.
MAX_CLASSES = 255
# Above this many agents and lines, the Model tab leaves the space to the Map tab.
MATPLOTLIB_LIMIT = 10_000
# Up to this many agents, the Map tab colours them with the session's portrayal.
PORTRAYAL_LIMIT = 20_000
HIDDEN = "none"
ALPHA = 3
BYTE = 255


@dataclass
class Scene:
    """Flat arrays of one model state, in coordinates shifted to start at ``origin``."""

    points: np.ndarray
    classes: np.ndarray
    legend: list[tuple[str, str]]
    nodes: np.ndarray = field(default_factory=lambda: np.zeros((0, XY), FLOAT))
    segments: np.ndarray = field(default_factory=lambda: np.zeros((0, SEGMENT), FLOAT))
    origin: tuple[float, float] = (0.0, 0.0)
    extent: tuple[float, float] = (1.0, 1.0)
    colours: np.ndarray | None = None

    @property
    def size(self) -> int:
        """How many points, nodes and lines the scene holds."""
        return len(self.points) + len(self.nodes) + len(self.segments)


def _class_indices(agents: list) -> tuple[np.ndarray, list[tuple[str, str]]]:
    """Each agent's class index, and the legend: class names in order, with colours."""
    names = [type(agent).__name__ for agent in agents]
    ordered = sorted(set(names))
    index = {name: min(i, MAX_CLASSES) for i, name in enumerate(ordered)}
    legend = [(n, OKABE_ITO[i % len(OKABE_ITO)]) for n, i in index.items()]
    return np.fromiter((index[n] for n in names), CLASS_INDEX, len(names)), legend


def portrayal_colours(agents: list, portrayal: Callable) -> np.ndarray:
    """Each agent's portrayal colour as RGBA bytes; an agent it returns None for is hidden."""
    styles = [portrayal(agent) for agent in agents]
    names = [getattr(s, "color", None) or HIDDEN for s in styles]
    rgba = to_rgba_array(names)
    rgba[[s is None for s in styles], ALPHA] = 0.0
    return np.round(rgba * BYTE).astype(np.uint8)


def _cell_points(agents: list) -> tuple[np.ndarray, list]:
    """The positions of the cells of the agents that stand on one, and those agents."""
    placed = [a for a in agents if getattr(a, "cell", None) is not None]
    points = np.array([a.cell.position[:XY] for a in placed], dtype=float)
    return points.reshape(-1, XY), placed


def _network_lines(space: Any) -> tuple[np.ndarray, np.ndarray]:
    """A network's node positions and its edges as segments."""
    cells = space._cells
    order = {node: i for i, node in enumerate(cells)}
    nodes = np.array([cell.position[:XY] for cell in cells.values()], dtype=float)
    nodes = nodes.reshape(-1, XY)
    pairs = np.array(
        [(order[a], order[b]) for a, b in space.G.edges() if a in order and b in order],
        dtype=np.int64,
    ).reshape(-1, XY)
    return nodes, np.hstack([nodes[pairs[:, 0]], nodes[pairs[:, 1]]])


def _region_lines(regions: Any) -> np.ndarray:
    """The outlines of a GeoDataFrame's polygons, as segments."""
    import shapely  # noqa: PLC0415 (the geo extra; only GeoSpace has regions)

    if regions is None or regions.empty:
        return np.zeros((0, SEGMENT))
    rings = shapely.get_parts(shapely.boundary(regions.geometry.to_numpy()))
    coords, owner = shapely.get_coordinates(rings, return_index=True)
    same = owner[1:] == owner[:-1]
    return np.hstack([coords[:-1][same], coords[1:][same]])


def _space_arrays(space: Any, agents: list) -> tuple[np.ndarray, list, dict]:
    """The agents' points, the agents drawn, and the space's nodes and segments."""
    extras: dict[str, np.ndarray] = {}
    if hasattr(space, "agent_positions"):  # continuous and geographic spaces
        points = np.asarray(space.agent_positions, dtype=float)[:, :XY]
        drawn = list(space.active_agents)
        if getattr(space, "regions", None) is not None:
            extras["segments"] = _region_lines(space.regions)
        return points, drawn, extras
    points, drawn = _cell_points(agents)
    if hasattr(space, "G"):  # networks
        extras["nodes"], extras["segments"] = _network_lines(space)
    return points, drawn, extras


def _bounds(arrays: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """The lower-left and upper-right corners of every coordinate in ``arrays``."""
    found = [a.reshape(-1, XY) for a in arrays if a.size]
    if not found:
        return np.zeros(XY), np.ones(XY)
    stacked = np.vstack(found)
    return stacked.min(axis=0), stacked.max(axis=0)


def scene_of(model: Model, portrayal: Callable | None = None) -> Scene | None:
    """The scene of ``model``'s space, or None when it has no space.

    With a ``portrayal`` and at most ``PORTRAYAL_LIMIT`` agents, each point takes its
    portrayal's colour; otherwise each class has its colour.
    """
    space = model_space(model)
    if space is None:
        return None
    points, drawn, extras = _space_arrays(space, list(model.agents))
    classes, legend = _class_indices(drawn)
    colours = None
    if portrayal is not None and len(drawn) <= PORTRAYAL_LIMIT:
        colours = portrayal_colours(drawn, portrayal)
    nodes = extras.get("nodes", np.zeros((0, XY)))
    segments = extras.get("segments", np.zeros((0, SEGMENT)))
    low, high = _bounds([points, nodes, segments])
    shift = np.tile(low, SEGMENT // XY)
    return Scene(
        points=(points - low).astype(FLOAT),
        classes=classes,
        legend=legend,
        nodes=(nodes - low).astype(FLOAT),
        segments=(segments - shift).astype(FLOAT),
        origin=(float(low[0]), float(low[1])),
        extent=(float(high[0] - low[0]), float(high[1] - low[1])),
        colours=colours,
    )


def element_count(model: Model) -> int:
    """Agents plus network edges: what drawing the model's space costs, roughly."""
    space = model_space(model)
    graph = getattr(space, "G", None)
    return len(model.agents) + (graph.number_of_edges() if graph is not None else 0)


def _base64(array: np.ndarray) -> str:
    """``array``'s bytes as base64 text."""
    return base64.b64encode(np.ascontiguousarray(array).tobytes()).decode("ascii")


def encode(scene: Scene) -> dict[str, Any]:
    """The scene as the browser reads it: base64 buffers, counts, extent and palette."""
    return {
        "points": _base64(scene.points),
        "classes": _base64(scene.classes),
        "colours": "" if scene.colours is None else _base64(scene.colours),
        "nodes": _base64(scene.nodes),
        "segments": _base64(scene.segments),
        "counts": [len(scene.points), len(scene.nodes), len(scene.segments)],
        "extent": list(scene.extent),
        "palette": [colour for _, colour in scene.legend],
    }


__all__ = [
    "MATPLOTLIB_LIMIT",
    "PORTRAYAL_LIMIT",
    "Scene",
    "element_count",
    "encode",
    "portrayal_colours",
    "scene_of",
]
