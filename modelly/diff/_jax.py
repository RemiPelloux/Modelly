"""JAX, imported on first use: ``import modelly.diff`` works without it installed.

``jax`` and ``jnp`` here are stand-ins that import the real module the first
time an attribute is read, with an ImportError naming the ``diff`` extra when
JAX is missing. Every module of ``modelly.diff`` uses them instead of
importing JAX at the top, so listing the public API never needs JAX.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

from modelly._optional import require

EXTRA = "diff"


class LazyModule:
    """A module imported on first attribute access."""

    def __init__(self, name: str) -> None:
        """Remember the module's dotted name."""
        self._name = name
        self._module: ModuleType | None = None

    def __getattr__(self, attribute: str) -> Any:
        """Import the module (once) and read ``attribute`` from it."""
        if attribute.startswith("__"):
            raise AttributeError(attribute)
        if self._module is None:
            self._module = require(self._name, EXTRA)
        return getattr(self._module, attribute)


jax = LazyModule("jax")
jnp = LazyModule("jax.numpy")
