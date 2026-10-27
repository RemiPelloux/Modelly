"""Synthetic populations from census-style marginals (moved to ``modelly.population``).

Kept so that ``modelly.space.geo.population.ipf`` and ``synthesize_population`` go on
working; the toolkit, with households, places and contact networks, is
``modelly.population``.
"""

from modelly.population.fitting import (  # noqa: F401 - the constants stay importable
    MAX_ITERATIONS,
    REGION,
    TOLERANCE,
    ipf,
    synthesize_population,
)

__all__ = ["ipf", "synthesize_population"]
