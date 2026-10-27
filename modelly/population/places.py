"""Homes, schools and workplaces: where synthetic people live, study and work.

``locate_households`` puts every household at one random point of its region (all its
members share it). ``assign_places`` then sends the people who attend a kind of place
(pupils to schools, workers to workplaces) to the nearest place that still has room,
in random order, never farther than a maximum distance: people with no place within
reach get ``-1``. Distances are straight lines in the coordinates' units (metres in a
projected CRS such as a ``GeoSpace``'s).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from modelly.population.fitting import REGION
from modelly.population.households import DEFAULT_COLUMN, HOUSEHOLD

NO_PLACE = -1
X, Y = "x", "y"
CAPACITY = "capacity"
# People ranked against every place at once, per block: bounds the distance matrix.
BLOCK = 4096


@dataclass(frozen=True)
class PlaceSpec:
    """Who attends a kind of place, and how far they may travel to it.

    Attributes:
        name: the column of people that receives the place (``"school"``, ``"work"``).
        members: the levels of ``column`` whose people attend.
        column: the attribute ``members`` refers to.
        max_distance: nobody is sent farther than this; unlimited by default.
    """

    name: str
    members: Sequence[Any]
    column: str = DEFAULT_COLUMN
    max_distance: float = np.inf


def locate_households(
    people: pd.DataFrame, space: Any, rng: np.random.Generator
) -> pd.DataFrame:
    """A copy of ``people`` with ``x`` and ``y``: one random point per household.

    Args:
        people: one row per person, with ``region`` and ``household`` columns.
        space: a ``GeoSpace`` whose regions are the people's regions (anything with
            ``random_points(region, n, rng)`` returning an ``(n, 2)`` array).
        rng: a numpy generator (``model.rng``).
    """
    xy = np.zeros((len(people), 2))
    households = people[HOUSEHOLD].to_numpy()
    for region, rows in people.groupby(REGION, sort=False).indices.items():
        homes, slot = np.unique(households[rows], return_inverse=True)
        points = np.asarray(space.random_points(region, homes.size, rng), dtype=float)
        xy[rows] = points[slot]
    located = people.copy()
    located[X], located[Y] = xy[:, 0], xy[:, 1]
    return located


def assign_places(
    people: pd.DataFrame,
    places: pd.DataFrame,
    spec: PlaceSpec,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """A copy of ``people`` with a ``spec.name`` column: the row of ``places``, or ``-1``.

    Args:
        people: one row per person, with ``x``, ``y`` and ``spec.column``.
        places: one row per place, with ``x``, ``y`` and ``capacity`` (people it takes).
        spec: who attends and how far they may go.
        rng: a numpy generator (``model.rng``): the order in which people choose.

    Returns:
        the copy; a person's place is ``places.iloc[place]``. Everybody else gets ``-1``.
    """
    attending = np.isin(people[spec.column].to_numpy(), list(spec.members))
    order = rng.permutation(np.flatnonzero(attending))
    homes = people[[X, Y]].to_numpy(dtype=float)
    sites = places[[X, Y]].to_numpy(dtype=float)
    free = places[CAPACITY].to_numpy(dtype=np.int64).copy()
    chosen = np.full(len(people), NO_PLACE, dtype=np.int64)
    for start in range(0, order.size, BLOCK):
        block = order[start : start + BLOCK]
        distance = np.hypot(*(homes[block, np.newaxis, :] - sites).transpose(2, 0, 1))
        ranked = np.argsort(distance, axis=1, kind="stable")
        for person, ranks, row in zip(block, ranked, distance):
            chosen[person] = _nearest_free(ranks, row, free, spec.max_distance)
    assigned = people.copy()
    assigned[spec.name] = chosen
    return assigned


def _nearest_free(
    ranks: np.ndarray, distance: np.ndarray, free: np.ndarray, reach: float
) -> int:
    """The nearest place with room within ``reach``, its room taken; else ``NO_PLACE``."""
    for place in ranks:
        if distance[place] > reach:
            return NO_PLACE
        if free[place] > 0:
            free[place] -= 1
            return int(place)
    return NO_PLACE
