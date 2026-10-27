"""NetLogo's named colors, as the numbers NetLogo uses for them.

A NetLogo color is a number from 0 to 140: each base color is a multiple of ten plus
five, and ``red - 3.5`` is a darker red. Translated models compare and store these
numbers, so ``set pcolor red`` becomes ``patch.pcolor = RED``.
"""

from __future__ import annotations

__all__ = [
    "BASE_COLORS",
    "BLACK",
    "BLUE",
    "BROWN",
    "CYAN",
    "GRAY",
    "GREEN",
    "LIME",
    "MAGENTA",
    "NAMES",
    "ORANGE",
    "PINK",
    "RED",
    "SKY",
    "TURQUOISE",
    "VIOLET",
    "WHITE",
    "YELLOW",
]

BLACK = 0
GRAY = 5
WHITE = 9.9
RED = 15
ORANGE = 25
BROWN = 35
YELLOW = 45
GREEN = 55
LIME = 65
TURQUOISE = 75
CYAN = 85
SKY = 95
BLUE = 105
VIOLET = 115
MAGENTA = 125
PINK = 135

# The colors create-turtles picks from when no color is set.
BASE_COLORS = (
    *(GRAY, RED, ORANGE, BROWN, YELLOW, GREEN, LIME),
    *(TURQUOISE, CYAN, SKY, BLUE, VIOLET, MAGENTA, PINK),
)

# NetLogo name -> the constant of this module that holds its number.
NAMES = {
    "black": "BLACK",
    "gray": "GRAY",
    "grey": "GRAY",
    "white": "WHITE",
    "red": "RED",
    "orange": "ORANGE",
    "brown": "BROWN",
    "yellow": "YELLOW",
    "green": "GREEN",
    "lime": "LIME",
    "turquoise": "TURQUOISE",
    "cyan": "CYAN",
    "sky": "SKY",
    "blue": "BLUE",
    "violet": "VIOLET",
    "magenta": "MAGENTA",
    "pink": "PINK",
}
