"""Synthetic populations from census-style marginals: moved to ``modelly.population``.

Deprecated in 1.4, removed in 2.0. ``ipf`` and ``synthesize_population`` (here and on
``modelly.space.geo``) and the constants ``MAX_ITERATIONS``, ``REGION`` and
``TOLERANCE`` keep working and warn, naming their home in ``modelly.population``;
the toolkit, with households, places and contact networks, is ``modelly.population``.
"""

from __future__ import annotations

from typing import Any

import modelly.population
from modelly._deprecation import deprecated
from modelly.population import fitting

FUNCTIONS = ("ipf", "synthesize_population")
CONSTANTS = ("MAX_ITERATIONS", "REGION", "TOLERANCE")
# deprecated() -> moved() -> a module __getattr__ -> the code that named the old path.
_TO_USER = 3

__all__ = list(FUNCTIONS)


def moved(module: str, name: str) -> Any:
    """``name`` from its new home, warning that ``module.name`` is deprecated.

    Raises:
        AttributeError: if ``name`` is not one of the moved names.
    """
    if name not in FUNCTIONS + CONSTANTS:
        raise AttributeError(f"module {module!r} has no attribute {name!r}")
    home = modelly.population if name in FUNCTIONS else fitting
    deprecated(f"{module}.{name}", f"{home.__name__}.{name}", stacklevel=_TO_USER)
    return getattr(home, name)


def __getattr__(name: str) -> Any:
    """The moved names, with a deprecation warning (PEP 562)."""
    return moved(__name__, name)
