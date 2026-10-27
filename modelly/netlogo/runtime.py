"""The model a translated NetLogo program runs in: the world, ``ask``, and the primitives.

``NetLogoModel`` builds the patches from the scenario's world fields, keeps ``ticks``
and a ``DataCollector`` that records the globals and the size of each breed at
``reset-ticks`` and every ``tick``. Every random draw goes through ``self.random``, so
a seed fixes the whole run, ``ask`` order included.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from functools import partial
from typing import Any, cast

from modelly.core.agent import Agent
from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.netlogo.agents import (
    FULL_TURN,
    TURTLE_DEFAULTS,
    Patch,
    Turtle,
    own_variables,
)
from modelly.netlogo.colors import BASE_COLORS
from modelly.scenarios.scenario import Scenario
from modelly.space.grid.grids import OrthogonalMooreGrid

__all__ = ["NetLogoModel", "NetLogoScenario", "count_breed"]

DEFAULT_EXTENT = 16  # NetLogo's default world: patches -16 to 16 on both axes
HALF_PATCH = 0.5
VON_NEUMANN = ((0, 1), (1, 0), (0, -1), (-1, 0))
MOORE = (*VON_NEUMANN, (1, 1), (1, -1), (-1, -1), (-1, 1))


class NetLogoScenario(Scenario):
    """The world: inclusive patch coordinates and whether it wraps. Sliders are added."""

    min_pxcor: int = -DEFAULT_EXTENT
    max_pxcor: int = DEFAULT_EXTENT
    min_pycor: int = -DEFAULT_EXTENT
    max_pycor: int = DEFAULT_EXTENT
    wrap: bool = True


def count_breed(model: NetLogoModel, cls: type) -> int:
    """How many turtles of breed ``cls`` the model has (a data collector reporter)."""
    return len(model.breed(cls))


def count_turtles(model: NetLogoModel) -> int:
    """How many turtles the model has (a data collector reporter)."""
    return len(model.turtles())


class NetLogoModel(Model[Any, Any]):
    """The world of patches, the turtles on it and the NetLogo primitives they use.

    Subclasses set ``patch_class``, ``turtle_class``, ``breeds`` (name, class pairs),
    ``sliders`` (copied from the scenario) and ``global_names`` (start at 0).
    """

    patch_class: type[Patch] = Patch
    turtle_class: type[Turtle] = Turtle
    breeds: tuple[tuple[str, type[Turtle]], ...] = ()
    sliders: tuple[str, ...] = ()
    global_names: tuple[str, ...] = ()

    def __init__(
        self, scenario: NetLogoScenario | type[NetLogoScenario] = NetLogoScenario
    ) -> None:
        """Build the world from ``scenario``, copy the sliders, zero the globals."""
        super().__init__(scenario=scenario)
        self.build_world()
        for name in self.sliders:
            setattr(self, name, getattr(self.scenario, name))
        self.reset_globals()
        self.ticks = 0
        self.datacollector = DataCollector(model_reporters=self.reporters())

    # The world.

    def build_world(self) -> None:
        """One patch per cell of a Moore grid, then each patch's neighbours."""
        params = self.scenario
        self.width = params.max_pxcor - params.min_pxcor + 1
        self.height = params.max_pycor - params.min_pycor + 1
        self.min_pxcor, self.max_pxcor = params.min_pxcor, params.max_pxcor
        self.min_pycor, self.max_pycor = params.min_pycor, params.max_pycor
        self.world: OrthogonalMooreGrid[Any] = OrthogonalMooreGrid(
            [self.width, self.height],
            torus=params.wrap,
            capacity=math.inf,
            random=self.random,
        )
        self.patch_index: dict[tuple[int, int], Patch] = {}
        for x in range(self.width):
            for y in range(self.height):
                cell = self.world[(x, y)]
                self.patch_index[(x, y)] = self.patch_class(self, cell)
        self.patches = list(self.patch_index.values())
        for patch in self.patches:
            patch.neighbors4 = self.around(patch, VON_NEUMANN)
            patch.neighbors8 = self.around(patch, MOORE)

    def around(self, patch: Patch, offsets: Iterable[tuple[int, int]]) -> list[Patch]:
        """The patches at ``offsets`` from ``patch`` that are inside the world."""
        found = (
            self.patch_at(patch.pxcor + dx, patch.pycor + dy) for dx, dy in offsets
        )
        return [neighbour for neighbour in found if neighbour is not None]

    def patch_coordinates(self, cell: Any) -> tuple[int, int]:
        """``(pxcor, pycor)`` of a grid cell."""
        x, y = cell.coordinate
        return x + self.min_pxcor, y + self.min_pycor

    def patch_at(self, pxcor: int, pycor: int) -> Patch | None:
        """The patch at ``(pxcor, pycor)``, wrapped when the world wraps, else None."""
        x, y = pxcor - self.min_pxcor, pycor - self.min_pycor
        if self.scenario.wrap:
            x, y = x % self.width, y % self.height
        return self.patch_index.get((x, y))

    def patch_of_cell(self, cell: Any) -> Patch:
        """The patch of a grid cell."""
        return self.patch_index[cell.coordinate]

    def patch_of(self, agent: Patch | Turtle) -> Patch:
        """``agent`` when it is a patch, else the patch the turtle stands on."""
        return agent if isinstance(agent, Patch) else agent.patch

    # Agent sets.

    def turtles(self) -> list[Turtle]:
        """Every turtle, of every breed."""
        groups = self.agents_by_type.items()
        found = [t for cls, group in groups if issubclass(cls, Turtle) for t in group]
        return cast(list[Turtle], found)

    def breed(self, cls: type[Turtle]) -> list[Turtle]:
        """The turtles of breed ``cls``."""
        found = self.agents_by_type.get(cls, ())
        return cast(list[Turtle], list(found))

    def turtles_here(self, agent: Patch | Turtle, cls: type = Turtle) -> list[Turtle]:
        """The turtles of class ``cls`` on the patch of ``agent``."""
        cell = self.patch_of(agent).site
        found = [other for other in cell.agents if isinstance(other, cls)]
        return cast(list[Turtle], found)

    def neighbors(self, agent: Patch | Turtle) -> list[Patch]:
        """The eight patches around the patch of ``agent`` (fewer at a closed edge)."""
        return self.patch_of(agent).neighbors8

    def neighbors4(self, agent: Patch | Turtle) -> list[Patch]:
        """The four patches beside the patch of ``agent`` (fewer at a closed edge)."""
        return self.patch_of(agent).neighbors4

    # Commands.

    def ask(self, agents: Any, body: Callable[[Any], Any]) -> None:
        """Run ``body`` for each agent in a new random order, skipping dead turtles.

        ``agents`` is one agent, a list, or None (``nobody``: nothing runs).
        """
        if agents is None:
            return
        group: list[Any] = [agents] if isinstance(agents, Agent) else list(agents)
        self.random.shuffle(group)
        for agent in group:
            if agent.alive:
                body(agent)

    def create(self, cls: type[Turtle] | None, count: float) -> list[Turtle]:
        """``count`` new turtles of ``cls`` on patch 0 0, random headings and colors."""
        origin = self.patch_at(0, 0) or self.patches[len(self.patches) // 2]
        return [self.new_turtle(cls, origin) for _ in range(int(count))]

    def sprout(
        self, patch: Patch, count: float, cls: type[Turtle] | None = None
    ) -> list[Turtle]:
        """``count`` new turtles of ``cls`` on ``patch``, random headings and colors."""
        return [self.new_turtle(cls, patch) for _ in range(int(count))]

    def new_turtle(self, cls: type[Turtle] | None, patch: Patch) -> Turtle:
        """One new turtle on ``patch`` with a random heading and base color."""
        turtle = (cls or self.turtle_class)(self, patch.site)
        turtle.heading = self.random.randrange(FULL_TURN)
        turtle.color = self.random.choice(BASE_COLORS)
        return turtle

    def hatch(
        self, parent: Turtle, count: float, cls: type[Turtle] | None = None
    ) -> list[Turtle]:
        """``count`` copies of ``parent`` (of breed ``cls`` if given) on its patch."""
        inherited = (*TURTLE_DEFAULTS, *own_variables(type(parent)))
        children: list[Turtle] = []
        for _ in range(int(count)):
            child = (cls or type(parent))(self, parent.cell)
            for name in inherited:
                if hasattr(child, name):
                    setattr(child, name, getattr(parent, name))
            children.append(child)
        return children

    def clear_all(self) -> None:
        """Remove every turtle, reset every patch and global, set ``ticks`` to 0."""
        for turtle in self.turtles():
            turtle.die()
        for patch in self.patches:
            patch.reset()
        self.reset_globals()
        self.ticks = 0

    def reset_globals(self) -> None:
        """Every global at 0, as NetLogo starts them."""
        for name in self.global_names:
            setattr(self, name, 0)

    def reset_ticks(self) -> None:
        """``ticks`` to 0, then record the data (NetLogo updates its plots here)."""
        self.ticks = 0
        self.datacollector.collect(self)

    def tick(self) -> None:
        """Advance ``ticks`` by one, then record the data."""
        self.ticks += 1
        self.datacollector.collect(self)

    def reporters(self) -> dict[str, Any]:
        """The data collector's reporters: ticks, each global, each breed's size, turtles."""
        found: dict[str, Any] = {"ticks": "ticks"}
        found.update((name, name) for name in self.global_names)
        for name, cls in self.breeds:
            found[name] = partial(count_breed, cls=cls)
        if self.breeds or self.turtle_class is not Turtle:
            found["turtles"] = count_turtles
        return found

    # Reporters.

    def one_of(self, agents: Any) -> Any:
        """A random member of ``agents``; None (``nobody``) when there is none."""
        if agents is None or isinstance(agents, Agent):
            return agents
        group = list(agents)
        return self.random.choice(group) if group else None

    def random_int(self, limit: float) -> int:
        """NetLogo's ``random``: an integer from 0 up to ``limit``, away from 0."""
        bound = int(limit)
        if bound == 0:
            return 0
        draw = self.random.randrange(abs(bound))
        return draw if bound > 0 else -draw

    def random_float(self, limit: float) -> float:
        """A float from 0 up to ``limit``."""
        return float(self.random.random() * limit)

    def random_xcor(self) -> float:
        """A random x coordinate anywhere in the world."""
        low = self.min_pxcor - HALF_PATCH
        return float(low + self.random.random() * self.width)

    def random_ycor(self) -> float:
        """A random y coordinate anywhere in the world."""
        low = self.min_pycor - HALF_PATCH
        return float(low + self.random.random() * self.height)

    def random_pxcor(self) -> int:
        """A random patch x coordinate."""
        return self.random.randrange(self.min_pxcor, self.max_pxcor + 1)

    def random_pycor(self) -> int:
        """A random patch y coordinate."""
        return self.random.randrange(self.min_pycor, self.max_pycor + 1)
