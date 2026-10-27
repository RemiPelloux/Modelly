"""The interface tab of a ``.nlogo`` file: sliders and switches, and the world's size.

A ``.nlogo`` file is sections separated by ``@#$#@#$#@``: the code tab first, the
interface second. Each interface widget is a block of lines, its type first. Sliders
and switches become Scenario fields; the view (``GRAPHICS-WINDOW``) gives the patch
coordinates and whether the world wraps. Choosers and input boxes are reported.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["SECTION", "Field", "Interface", "World", "parse_interface"]

SECTION = "@#$#@#$#@"
# Line numbers inside a widget block, the type line being 0.
SLIDER_VARIABLE, SLIDER_MIN, SLIDER_MAX, SLIDER_VALUE, SLIDER_STEP = 6, 7, 8, 9, 10
SWITCH_VARIABLE, SWITCH_STATE = 6, 7
SWITCH_ON = "0"  # NetLogo stores an "on" switch as 0
WINDOW_WRAP_X, WINDOW_WRAP_Y = 14, 15
WINDOW_MIN_PXCOR, WINDOW_MAX_PXCOR, WINDOW_MIN_PYCOR, WINDOW_MAX_PYCOR = 17, 18, 19, 20
NAMED_WIDGETS = {"CHOOSER": 6, "INPUTBOX": 5}  # reported: type -> line of the name
DEFAULT_EXTENT = 16  # NetLogo's default world: patches -16 to 16 on both axes


@dataclass(frozen=True)
class World:
    """The patch coordinates, inclusive, and whether each axis wraps."""

    min_pxcor: int = -DEFAULT_EXTENT
    max_pxcor: int = DEFAULT_EXTENT
    min_pycor: int = -DEFAULT_EXTENT
    max_pycor: int = DEFAULT_EXTENT
    wrap: bool = True


@dataclass(frozen=True)
class Field:
    """A slider or switch: its NetLogo name, Python type name and default value."""

    name: str
    kind: str  # "int", "float" or "bool"
    default: int | float | bool


@dataclass
class Interface:
    """What the interface tab gives the translated model."""

    fields: list[Field] = field(default_factory=list)
    world: World = field(default_factory=World)
    skipped: list[str] = field(default_factory=list)  # widgets left for a human


def number(text: str) -> int | float:
    """``text`` as an int when it is integral, else as a float."""
    value = float(text)
    return int(value) if value.is_integer() else value


def slider(lines: list[str]) -> Field:
    """A slider: an int field when its bounds, step and value are all integral."""
    texts = [lines[i] for i in (SLIDER_MIN, SLIDER_MAX, SLIDER_VALUE, SLIDER_STEP)]
    try:
        values = [float(text) for text in texts]
    except ValueError:  # a bound given as a variable: only the value counts
        values = [float(lines[SLIDER_VALUE])]
    integral = all(value.is_integer() for value in values)
    default = number(lines[SLIDER_VALUE])
    if integral:
        return Field(lines[SLIDER_VARIABLE].lower(), "int", int(default))
    return Field(lines[SLIDER_VARIABLE].lower(), "float", float(default))


def window(lines: list[str]) -> World:
    """The world of a ``GRAPHICS-WINDOW`` block; the default world when it is short."""
    if len(lines) <= WINDOW_MAX_PYCOR:
        return World()
    low_x, high_x = int(lines[WINDOW_MIN_PXCOR]), int(lines[WINDOW_MAX_PXCOR])
    low_y, high_y = int(lines[WINDOW_MIN_PYCOR]), int(lines[WINDOW_MAX_PYCOR])
    wraps = lines[WINDOW_WRAP_X] == "1" and lines[WINDOW_WRAP_Y] == "1"
    return World(low_x, high_x, low_y, high_y, wrap=wraps)


def blocks(text: str) -> list[list[str]]:
    """The widget blocks of an interface section: stripped lines, no blank ones."""
    found, current = [], []
    for line in [*text.splitlines(), ""]:
        if line.strip():
            current.append(line.strip())
        elif current:
            found.append(current)
            current = []
    return found


def parse_interface(text: str) -> Interface:
    """The sliders, switches and world of an interface section."""
    interface = Interface()
    for lines in blocks(text):
        kind = lines[0]
        if kind == "SLIDER" and len(lines) > SLIDER_STEP:
            interface.fields.append(slider(lines))
        elif kind == "SWITCH" and len(lines) > SWITCH_STATE:
            on = lines[SWITCH_STATE] == SWITCH_ON
            interface.fields.append(Field(lines[SWITCH_VARIABLE].lower(), "bool", on))
        elif kind == "GRAPHICS-WINDOW":
            interface.world = window(lines)
        elif kind in NAMED_WIDGETS and len(lines) > NAMED_WIDGETS[kind]:
            interface.skipped.append(f"{kind} {lines[NAMED_WIDGETS[kind]]}")
    return interface
