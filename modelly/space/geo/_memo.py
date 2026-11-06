"""One-entry memos kept on an object, for values rebuilt from the same inputs on every call.

A pyproj ``Transformer`` costs about 60 microseconds to build and an affine
inverse a few; a space or raster usually converts from one CRS, so remembering the last
inputs (compared by identity, never by value) and their result answers almost
every call. Owners drop ``MEMO_KEYS`` from their pickled state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pyproj

TRANSFORMER = "_transformer_memo"
INVERSE = "_inverse_memo"
TREE_ROWS = "_tree_rows_memo"
MEMO_KEYS = (TRANSFORMER, INVERSE, TREE_ROWS)


def memo(owner: Any, name: str, inputs: tuple, build: Callable[[], Any]) -> Any:
    """``build()``, reused while ``inputs`` are the very objects of the last call."""
    entry = owner.__dict__.get(name)
    if (
        entry is not None
        and len(entry[0]) == len(inputs)
        and all(old is new for old, new in zip(entry[0], inputs, strict=True))
    ):
        return entry[1]
    value = build()
    owner.__dict__[name] = (inputs, value)
    return value


def transformer(owner: Any, source: Any, target: Any) -> pyproj.Transformer:
    """``pyproj.Transformer.from_crs(source, target, always_xy=True)``, memoised on ``owner``."""
    return memo(
        owner,
        TRANSFORMER,
        (source, target),
        lambda: pyproj.Transformer.from_crs(source, target, always_xy=True),
    )


def without_memos(state: dict) -> dict:
    """``state`` with the memos removed (they hold unpicklable or derived values)."""
    for name in MEMO_KEYS:
        state.pop(name, None)
    return state
