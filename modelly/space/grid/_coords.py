"""The cell coordinate of a position on a grid: the floor of each component."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

# np.floor(position).astype(int) and math.floor agree on floats in this range.
INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1
_REAL_KINDS = frozenset("biuf")


def floor_coordinate(position: Any) -> tuple:
    """``tuple(np.floor(position).astype(int))``, in Python for a plain point.

    A 1-D numeric array, or a list or tuple of ints and floats, is floored
    element by element; anything else (or a value outside int64) takes numpy.
    """
    if isinstance(position, np.ndarray):
        values = position.tolist() if position.dtype.kind in _REAL_KINDS else None
    elif isinstance(position, (list, tuple)) and all(
        type(x) is float or type(x) is int for x in position
    ):
        values = position
    else:
        values = None
    if isinstance(values, (list, tuple)):
        try:
            coord = tuple([math.floor(x) for x in values])
        except (TypeError, ValueError, OverflowError):
            pass  # nested, NaN or infinite: numpy's answer, warnings included
        else:
            if all(INT64_MIN <= c <= INT64_MAX for c in coord):
                return coord
    return tuple(np.floor(position).astype(int))
