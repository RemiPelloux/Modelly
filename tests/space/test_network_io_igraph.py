"""Tests for from_igraph against a minimal stand-in of the igraph Graph API.

igraph is optional and usually absent, so the importer is exercised through an
object exposing just what it reads: ``vs``, ``es``, ``vcount`` and ``is_directed``.
"""

from modelly.space.networks.io import DEFAULT_LAYER, from_igraph


class _Seq:
    """A vertex or edge sequence: attribute columns plus iteration."""

    def __init__(self, items, columns):
        self._items = items
        self._columns = columns

    def attributes(self):
        return list(self._columns)

    def __getitem__(self, name):
        return self._columns[name]

    def __iter__(self):
        return iter(self._items)


class _Edge:
    def __init__(self, source, target, attributes):
        self.source, self.target = source, target
        self._attributes = attributes

    def __getitem__(self, name):
        return self._attributes[name]


class FakeGraph:
    """Just enough of ``igraph.Graph`` for from_igraph."""

    def __init__(self, n, edges, directed=False, names=None, **edge_columns):
        """Create the instance."""
        self._n = n
        self._directed = directed
        vertex_columns = {"name": names} if names is not None else {}
        self.vs = _Seq(list(range(n)), vertex_columns)
        records = [
            _Edge(u, v, {key: values[i] for key, values in edge_columns.items()})
            for i, (u, v) in enumerate(edges)
        ]
        self.es = _Seq(records, edge_columns)

    def vcount(self):
        """The number of vertices."""
        return self._n

    def is_directed(self):
        """Whether the edges are directed."""
        return self._directed


def test_named_vertices_layers_and_weights():
    """Named vertices layers and weights."""
    graph = FakeGraph(
        3,
        [(0, 1), (1, 2)],
        names=["a", "b", "c"],
        layer=["home", 7],
        weight=[2.0, 3.0],
    )
    network = from_igraph(graph, layer_attribute="layer")
    assert sorted(network.layers) == ["7", "home"]
    assert network.weighted_neighbors("b") == {"a": 2.0, "c": 3.0}
    assert not network.directed


def test_unnamed_vertices_default_layer_and_weight():
    """Unnamed vertices default layer and weight."""
    graph = FakeGraph(3, [(0, 2)], directed=True)
    network = from_igraph(graph)
    assert network.directed
    assert network.layers == [DEFAULT_LAYER]
    assert list(network.edges(DEFAULT_LAYER)) == [(0, 2, 1.0)]


def test_missing_layer_attribute_and_custom_weight_name():
    """Missing layer attribute and custom weight name."""
    graph = FakeGraph(2, [(0, 1)], strength=[4.5])
    network = from_igraph(graph, layer_attribute="layer", weight="strength")
    assert network.layers == [DEFAULT_LAYER]
    assert list(network.edges(DEFAULT_LAYER)) == [(0, 1, 4.5)]
