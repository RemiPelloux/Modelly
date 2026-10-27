"""Contact networks from places: who meets whom at home, at school and at work.

``contact_network`` links the people who share a place on one layer per kind of place,
in a ``MultilayerNetwork`` (``modelly.space.networks``): everybody in a household knows
everybody else in it; pupils of a school are split at random into classes, and workers of
a workplace into teams, each a clique. Node ``i`` is the ``i``-th row of ``people``, so
``contact_matrix(network, groups)`` gives the mean contacts between age groups for an
age-structured model, and ``network.adjacency() @ infected`` drives a network epidemic.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
import pandas as pd

from modelly.population.households import HOUSEHOLD
from modelly.population.places import NO_PLACE
from modelly.space.networks.multilayer import MultilayerNetwork

SCHOOL, WORK = "school", "work"
LAYER_WEIGHTS = {HOUSEHOLD: 1.0, SCHOOL: 0.5, WORK: 0.25}
CLASS_SIZE = 25
TEAM_SIZE = 10


@dataclass(frozen=True)
class ContactLayers:
    """The layers of a contact network and the size of the cliques on each.

    Attributes:
        weights: layer name to its weight; each name is a column of people holding the
            place (household, school, workplace) of every person, ``-1`` for none.
        group_sizes: layer name to the people per clique within one place (a class, a
            team); a layer not listed links everybody who shares a place.
    """

    weights: Mapping[str, float] = field(default_factory=lambda: dict(LAYER_WEIGHTS))
    group_sizes: Mapping[str, int] = field(
        default_factory=lambda: {SCHOOL: CLASS_SIZE, WORK: TEAM_SIZE}
    )


def contact_network(
    people: pd.DataFrame,
    rng: np.random.Generator,
    layers: ContactLayers | None = None,
) -> MultilayerNetwork:
    """A ``MultilayerNetwork`` over the rows of ``people``, one layer per kind of place.

    Args:
        people: one row per person, with one column per layer (see ``ContactLayers``).
        rng: a numpy generator (``model.rng``) to split places into classes and teams.
        layers: the layers, their weights and clique sizes; household (1.0), school
            (0.5, classes of 25) and work (0.25, teams of 10) by default.
    """
    layers = ContactLayers() if layers is None else layers
    network = MultilayerNetwork(len(people), dict(layers.weights))
    for layer in layers.weights:
        size = layers.group_sizes.get(layer)
        for members in place_groups(people[layer].to_numpy(), size, rng):
            network.add_edges(combinations(members.tolist(), 2), layer)
    return network


def place_groups(
    places: np.ndarray, size: int | None, rng: np.random.Generator
) -> list[np.ndarray]:
    """The rows that share each place, in place order, split at random into ``size`` groups.

    Args:
        places: the place of every row; ``-1`` (no place) is left out.
        size: people per group within a place; ``None`` keeps each place whole.
        rng: a numpy generator, used only when ``size`` is given.
    """
    order = np.argsort(places, kind="stable")
    ids, starts = np.unique(places[order], return_index=True)
    groups = []
    for place, members in zip(ids, np.split(order, starts[1:])):
        if place == NO_PLACE or members.size == 0:
            continue
        if size is None:
            groups.append(members)
            continue
        shuffled = rng.permutation(members)
        groups.extend(np.split(shuffled, np.arange(size, members.size, size)))
    return groups
