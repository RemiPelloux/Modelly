"""Tests for the runtime of translated models: the world, turtles and primitives."""

import pytest

from modelly.netlogo.agents import Turtle, offset
from modelly.netlogo.runtime import NetLogoModel, NetLogoScenario

EXTENT = 2  # a 5 x 5 world, patches -2 to 2


def world(wrap: bool = True, seed: int = 1) -> NetLogoModel:
    """A small model with no program, just the world."""
    scenario = NetLogoScenario(
        rng=seed,
        wrap=wrap,
        min_pxcor=-EXTENT,
        max_pxcor=EXTENT,
        min_pycor=-EXTENT,
        max_pycor=EXTENT,
    )
    return NetLogoModel(scenario)


def test_patches_and_neighbours():
    """One patch per cell; four and eight neighbours, fewer at a closed edge."""
    model = world()
    assert len(model.patches) == (2 * EXTENT + 1) ** 2
    corner = model.patch_at(-EXTENT, -EXTENT)
    assert (corner.pxcor, corner.pycor) == (-EXTENT, -EXTENT)
    assert len(corner.neighbors4) == 4 and len(corner.neighbors8) == 8
    assert model.patch_at(EXTENT + 1, 0) is model.patch_at(-EXTENT, 0)
    closed = world(wrap=False)
    corner = closed.patch_at(-EXTENT, -EXTENT)
    assert len(corner.neighbors4) == 2 and len(corner.neighbors8) == 3
    assert closed.patch_at(EXTENT + 1, 0) is None


def test_headings_snap_to_the_eight_neighbours():
    """0 is north, 90 east; a heading rounds to the nearest multiple of 45."""
    assert offset(0) == (0, 1) and offset(90) == (1, 0)
    assert offset(180) == (0, -1) and offset(270) == (-1, 0)
    assert offset(40) == (1, 1) and offset(350) == (0, 1)


def test_turtle_moves_turns_and_stops_at_a_closed_edge():
    """``fd`` moves whole patches, wraps or stops at the edge; ``rt``/``lt`` turn."""
    model = world(wrap=False)
    (turtle,) = model.create(None, 1)
    turtle.heading = 90
    turtle.forward(1)
    assert (turtle.xcor, turtle.ycor) == (1, 0)
    turtle.forward(5)
    assert turtle.xcor == EXTENT
    turtle.forward(-1)
    assert turtle.xcor == EXTENT - 1
    turtle.left(90)
    turtle.right(45)
    assert turtle.heading == 45
    turtle.setxy(-1.4, 1.6)
    assert (turtle.xcor, turtle.ycor) == (-1, 2)
    with pytest.raises(ValueError, match="outside"):
        turtle.setxy(10, 0)
    turtle.move_to_agent(model.patch_at(0, 0))
    assert turtle.patch is model.patch_at(0, 0)


def test_ask_skips_dead_turtles_and_nobody():
    """A turtle killed by an earlier one does not act; ``nobody`` asks no one."""
    model = world()
    turtles = model.create(None, 4)
    acted = []

    def body(turtle):
        """Kill every other turtle, then record who acted."""
        for other in model.turtles_here(turtle):
            if other is not turtle:
                other.die()
        acted.append(turtle)

    model.ask(turtles, body)
    assert len(acted) == 1 and len(model.turtles()) == 1
    model.ask(None, body)
    assert len(acted) == 1


def test_random_primitives_and_hatch():
    """``random`` follows NetLogo's sign rule; ``hatch`` copies the parent."""
    model = world()
    assert model.random_int(0) == 0
    assert all(0 <= model.random_int(3) < 3 for _ in range(50))
    assert all(-3 < model.random_int(-3) <= 0 for _ in range(50))
    assert all(-EXTENT <= model.random_pxcor() <= EXTENT for _ in range(50))
    assert model.one_of([]) is None
    (parent,) = model.create(None, 1)
    parent.heading, parent.color = 30, 15
    (child,) = model.hatch(parent, 1)
    assert isinstance(child, Turtle) and child is not parent
    assert (child.heading, child.color, child.cell) == (30, 15, parent.cell)
    model.clear_all()
    assert model.turtles() == [] and model.ticks == 0
