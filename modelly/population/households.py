"""Households: synthetic people grouped by a household-size distribution, each with a head.

Census tables give, per region, how many households have one, two, three... members.
``assign_households`` draws that many households for the people of each region (rounded
to whole households with ``trs``, then grown or shrunk one member at a time until they
hold exactly the region's people), gives every household a head among the people who can
head one (adults), and spreads everybody else over the remaining places at random. The
people, and so their marginals, are unchanged: only a ``household`` column is added.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from modelly.population.fitting import REGION, trs

HOUSEHOLD = "household"
DEFAULT_COLUMN = "age"
SINGLE = 1


@dataclass(frozen=True)
class HouseholdSpec:
    """How to group the people of each region into households.

    Attributes:
        sizes: region label to the shares (or counts) of households with 1, 2, ..., k
            members; only the proportions matter.
        heads: the levels of ``column`` whose people can head a household (adults).
        column: the attribute ``heads`` refers to.
    """

    sizes: Mapping[Any, Sequence[float]]
    heads: Sequence[Any]
    column: str = DEFAULT_COLUMN


def household_sizes(
    people: int, shares: Sequence[float], rng: np.random.Generator
) -> np.ndarray:
    """Sizes of households that hold exactly ``people`` people, in random order.

    Args:
        people: the number of people to house.
        shares: the shares (or counts) of households with 1, 2, ..., k members.
        rng: a numpy generator (``model.rng``).

    Returns:
        an ``int64`` array of household sizes between 1 and k that sums to ``people``.
    """
    shares = np.asarray(shares, dtype=float)
    shares = shares / shares.sum()
    levels = np.arange(SINGLE, shares.size + SINGLE)
    if people == 0:
        return np.zeros(0, dtype=np.int64)
    total = max(SINGLE, round(people / float(levels @ shares)))
    sizes = rng.permutation(np.repeat(levels, trs(total * shares, rng)))
    return _match(sizes, people, int(levels[-1]), rng)


def assign_households(
    people: pd.DataFrame, spec: HouseholdSpec, rng: np.random.Generator
) -> pd.DataFrame:
    """A copy of ``people`` with a ``household`` column: ids unique across regions.

    Args:
        people: one row per person, with a ``region`` column and ``spec.column``.
        spec: the household sizes per region and who can head a household.
        rng: a numpy generator (``model.rng``).

    Raises:
        ValueError: if a region has more households than people who can head one.
    """
    ids = np.full(len(people), -1, dtype=np.int64)
    can_head = np.isin(people[spec.column].to_numpy(), list(spec.heads))
    offset = 0
    for region, rows in people.groupby(REGION, sort=False).indices.items():
        sizes = household_sizes(rows.size, spec.sizes[region], rng)
        heads = rows[can_head[rows]]
        if heads.size < sizes.size:
            raise ValueError(
                f"Region {region!r} needs {sizes.size} household heads and has only "
                f"{heads.size} people who can head a household."
            )
        ids[rows] = offset + _members(rows, heads, sizes, rng)
        offset += sizes.size
    housed = people.copy()
    housed[HOUSEHOLD] = ids
    return housed


def _members(
    rows: np.ndarray, heads: np.ndarray, sizes: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """The household (0 .. len(sizes) - 1) of every row: one head each, the rest at random."""
    chosen = rng.choice(heads, size=sizes.size, replace=False)
    others = rng.permutation(np.setdiff1d(rows, chosen))
    household = np.zeros(rows.size, dtype=np.int64)
    household[np.searchsorted(rows, chosen)] = np.arange(sizes.size)
    slots = np.repeat(np.arange(sizes.size), sizes - SINGLE)
    household[np.searchsorted(rows, others)] = slots
    return household


def _match(
    sizes: np.ndarray, people: int, largest: int, rng: np.random.Generator
) -> np.ndarray:
    """Grow or shrink random households by one member until they hold ``people``."""
    sizes = sizes.astype(np.int64)
    gap = people - int(sizes.sum())
    while gap:
        step = 1 if gap > 0 else -1
        room = np.flatnonzero(sizes < largest if step > 0 else sizes > SINGLE)
        if room.size:
            sizes[rng.choice(room)] += step
        elif step > 0:
            sizes = np.append(sizes, SINGLE)
        else:
            sizes = sizes[:-1]
        gap -= step
    return sizes
