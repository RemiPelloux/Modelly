"""Translate NetLogo models to Modelly: ``python -m modelly.netlogo model.nlogo``.

The translator reads a well-defined subset of NetLogo (turtles, patches, breeds,
``ask``, ``set``, ``if``/``ifelse``, ``repeat``, the common movement and random
primitives, sliders and switches) and writes a Python module whose model runs on
``modelly.netlogo.runtime``. Anything outside the subset is kept as a ``# NETLOGO``
comment and listed in the report, so nothing is dropped silently. See
``docs/netlogo.md`` for the subset, the semantics and the limits.
"""

from modelly.netlogo._translate import Translation, translate

__all__ = ["Translation", "translate"]
