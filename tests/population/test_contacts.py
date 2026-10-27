"""Contact networks from places: cliques per household, class and team."""

import numpy as np
import pandas as pd

from modelly.population import ContactLayers, contact_network, place_groups
from modelly.space.networks import contact_matrix


def small_town():
    """Eight people: two households, one school of four pupils, one workplace."""
    return pd.DataFrame(
        {
            "household": [0, 0, 0, 0, 1, 1, 1, 1],
            "school": [0, 0, -1, -1, 0, 0, -1, -1],
            "work": [-1, -1, 0, 0, -1, -1, 0, -1],
        }
    )


def test_layers_are_cliques_of_the_places():
    """Households and the workplace are cliques; classes split the school."""
    people = small_town()
    layers = ContactLayers(group_sizes={"school": 2})
    network = contact_network(people, np.random.default_rng(1), layers)
    assert network.layers == ["household", "school", "work"]
    assert network.number_of_edges("household") == 2 * 6
    assert network.number_of_edges("work") == 3
    assert network.number_of_edges("school") == 2  # two classes of two
    assert not network.has_edge(6, 7, "work")  # 7 does not work
    for pupil in (0, 1, 4, 5):
        assert network.degree(pupil, "school") == 1


def test_contact_matrix_is_reciprocal():
    """Undirected layers give ``N(a) C[a, b] == N(b) C[b, a]``."""
    people = small_town()
    network = contact_network(people, np.random.default_rng(2))
    groups = np.array([0, 0, 1, 1, 0, 0, 1, 1])
    matrix = contact_matrix(network, groups)
    sizes = np.bincount(groups)[:, np.newaxis]
    np.testing.assert_allclose(sizes * matrix, (sizes * matrix).T)


def test_place_groups_skips_no_place_and_is_seeded():
    """``-1`` is nobody's place; the same seed splits places the same way."""
    places = np.array([2, -1, 2, 0, 2, 2, 0])
    whole = place_groups(places, None, np.random.default_rng(3))
    assert [g.tolist() for g in whole] == [[3, 6], [0, 2, 4, 5]]
    split = place_groups(places, 3, np.random.default_rng(3))
    assert sorted(len(g) for g in split) == [1, 2, 3]
    again = place_groups(places, 3, np.random.default_rng(3))
    assert all(np.array_equal(a, b) for a, b in zip(split, again))
