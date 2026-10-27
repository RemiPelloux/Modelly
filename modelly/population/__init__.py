"""Synthetic populations: people, households and places from aggregate census tables.

Pure numpy and pandas (``contact_network`` builds a ``modelly.space.networks`` network;
``locate_households`` takes a ``GeoSpace``, which needs the ``geo`` extra). A population
is built in steps, each adding columns to one DataFrame of people:

- ``synthesize_population``: people per region from marginal tables, by iterative
  proportional fitting (``ipf``) and truncate-replicate-sample rounding (``trs``);
  ``marginal_errors`` checks the result against the tables.
- ``anneal``: the combinatorial-optimisation alternative, choosing whole records
  (households) from a sample by simulated annealing to fit the tables.
- ``assign_households``: households from a household-size distribution, each with a head.
- ``locate_households`` and ``assign_places``: homes in their regions, then schools and
  workplaces, the nearest with room within a distance limit.
- ``contact_network``: household, school and work layers of a ``MultilayerNetwork``.

Privacy: everything here works from aggregate tables (counts per region and level), and
the people it makes are synthetic: no row is a real person. Modelly bundles no personal
data and no microdata. Aggregates of very small areas can still disclose people; use
published, disclosure-controlled tables, and do not publish a synthetic population
fitted to unpublished small counts.
"""

from modelly.population.annealing import Annealing, anneal, total_absolute_error
from modelly.population.contacts import ContactLayers, contact_network, place_groups
from modelly.population.fitting import (
    ipf,
    marginal_errors,
    synthesize_population,
    trs,
)
from modelly.population.households import (
    HouseholdSpec,
    assign_households,
    household_sizes,
)
from modelly.population.places import PlaceSpec, assign_places, locate_households

__all__ = [
    "Annealing",
    "ContactLayers",
    "HouseholdSpec",
    "PlaceSpec",
    "anneal",
    "assign_households",
    "assign_places",
    "contact_network",
    "household_sizes",
    "ipf",
    "locate_households",
    "marginal_errors",
    "place_groups",
    "synthesize_population",
    "total_absolute_error",
    "trs",
]
