"""Visualization backends for Modelly space rendering.

This module provides different backend implementations for visualizing
Modelly agent-based model spaces and components.

Note:
    These backends are used internally by the space renderer and are not intended for
    direct use by end users. See `SpaceRenderer` for actual usage and setting up
    visualizations.

Available Backends:
    1. AltairBackend
    2. MatplotlibBackend

"""

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # names for type checkers and linters; imported lazily at run time
    from modelly.viz.altair.backend import AltairBackend
    from modelly.viz.mpl.backend import MatplotlibBackend

# Imported on first use, so that the backends can import modelly.viz.render.portrayal.
_LAZY = {
    "AltairBackend": "modelly.viz.altair.backend",
    "MatplotlibBackend": "modelly.viz.mpl.backend",
}

__all__ = [
    "AltairBackend",
    "MatplotlibBackend",
]


def __getattr__(name: str):
    """Import a backend the first time it is asked for."""
    if name not in _LAZY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(_LAZY[name]), name)
