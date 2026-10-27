"""Patches and turtles: the two kinds of NetLogo agent, as Modelly agents.

A patch is an agent tied to one cell of an ``OrthogonalMooreGrid``; a turtle is a
``CellAgent`` standing on a cell. Turtles are patch-centred: ``fd 1`` moves one patch
in the direction of the heading, rounded to the nearest of the eight neighbours.
Variables declared with ``turtles-own``, ``<breed>-own`` and ``patches-own`` are listed
in each subclass's ``own`` tuple and start at 0, as in NetLogo.
"""

from __future__ import annotations

import math
from typing import Any

from modelly.core.agent import Agent
from modelly.netlogo.colors import BLACK, WHITE
from modelly.space.cells.agents import CellAgent

__all__ = ["Patch", "Turtle", "own_variables"]

FULL_TURN = 360
EIGHTH_TURN = 45
DIRECTIONS = 8
TURTLE_DEFAULTS = {
    "heading": 0,
    "color": BLACK,
    "shape": "default",
    "size": 1,
    "label": "",
    "label_color": WHITE,
    "hidden": False,
    "pen_size": 1,
    "pen_mode": "up",
}


def own_variables(cls: type) -> tuple[str, ...]:
    """The ``own`` variables of ``cls`` and of its bases, base classes first."""
    found: list[str] = []
    for klass in reversed(cls.__mro__):
        found.extend(name for name in vars(klass).get("own", ()) if name not in found)
    return tuple(found)


def offset(heading: float) -> tuple[int, int]:
    """The patch step of ``heading``: 0 is north, 90 east, rounded to a multiple of 45."""
    turn = round(heading / EIGHTH_TURN) % DIRECTIONS * EIGHTH_TURN
    radians = math.radians(turn)
    return round(math.sin(radians)), round(math.cos(radians))


class Patch(Agent[Any]):
    """One patch: a cell of the world with ``pcolor`` and the ``patches-own`` variables."""

    own: tuple[str, ...] = ()

    def __init__(self, model: Any, cell: Any) -> None:
        """Create the patch of ``cell``, black, its variables at 0."""
        super().__init__(model)
        self.site = cell
        pxcor, pycor = model.patch_coordinates(cell)
        self.pxcor: int = pxcor
        self.pycor: int = pycor
        self.alive = True  # patches never die; ask checks it for every agent
        self.neighbors4: list[Patch] = []
        self.neighbors8: list[Patch] = []
        self.reset()

    def reset(self) -> None:
        """Black, no label, every ``own`` variable at 0 (``clear-all``)."""
        self.pcolor = BLACK
        self.plabel = ""
        self.plabel_color = WHITE
        for name in own_variables(type(self)):
            setattr(self, name, 0)


class Turtle(CellAgent):
    """One turtle, on the patch of its cell, with a heading and the ``own`` variables."""

    own: tuple[str, ...] = ()
    # Set from TURTLE_DEFAULTS in __init__.
    heading: float
    color: float
    shape: str
    size: float
    label: str
    label_color: float
    hidden: bool
    pen_size: float
    pen_mode: str

    def __init__(self, model: Any, cell: Any) -> None:
        """Create a turtle on ``cell``, heading north, its variables at 0."""
        super().__init__(model)
        self.cell = cell
        self.alive = True
        for name, value in TURTLE_DEFAULTS.items():
            setattr(self, name, value)
        for name in own_variables(type(self)):
            setattr(self, name, 0)

    @property
    def patch(self) -> Patch:
        """The patch the turtle stands on (``patch-here``)."""
        patch: Patch = self.model.patch_of_cell(self.cell)
        return patch

    @property
    def xcor(self) -> int:
        """The x coordinate: the patch's, turtles being patch-centred."""
        return self.patch.pxcor

    @property
    def ycor(self) -> int:
        """The y coordinate: the patch's, turtles being patch-centred."""
        return self.patch.pycor

    @property
    def who(self) -> int:
        """The turtle's number: its unique id."""
        return int(self.unique_id)

    def forward(self, distance: float) -> None:
        """Move ``distance`` patches (rounded) along the heading; stop at a closed edge."""
        dx, dy = offset(self.heading if distance >= 0 else self.heading + FULL_TURN / 2)
        for _ in range(round(abs(distance))):
            here = self.patch
            target = self.model.patch_at(here.pxcor + dx, here.pycor + dy)
            if target is None:
                return
            self.cell = target.site

    def right(self, angle: float) -> None:
        """Turn clockwise by ``angle`` degrees."""
        self.heading = (self.heading + angle) % FULL_TURN

    def left(self, angle: float) -> None:
        """Turn anticlockwise by ``angle`` degrees."""
        self.heading = (self.heading - angle) % FULL_TURN

    def setxy(self, x: float, y: float) -> None:
        """Move to the patch nearest to the point ``(x, y)``.

        Raises:
            ValueError: when the point is outside a world that does not wrap.
        """
        target = self.model.patch_at(math.floor(x + 0.5), math.floor(y + 0.5))
        if target is None:
            raise ValueError(f"setxy {x} {y}: the point is outside the world")
        self.cell = target.site

    def move_to_agent(self, agent: Any) -> None:
        """Move to the patch of ``agent``, a patch or a turtle (``move-to``)."""
        self.cell = agent.site if isinstance(agent, Patch) else agent.cell

    def die(self) -> None:
        """Remove the turtle from the model; ``ask`` skips it from now on."""
        self.alive = False
        self.remove()  # type: ignore[no-untyped-call]  # CellAgent.remove is untyped
