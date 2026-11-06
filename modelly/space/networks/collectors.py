"""Cheap network statistics for data collection: degrees, clustering, components.

Every statistic takes a graph in any of the forms a model holds: a ``MultilayerNetwork``
or ``TemporalNetwork`` (its current combined adjacency), a ``Network`` cell space, a
NetworkX graph, an igraph graph or a scipy sparse matrix. The structure is read as a
simple undirected graph (weights, edge directions and self-loops are ignored), and the
work is a few sparse-matrix products, so a reporter costs milliseconds on large graphs.
On simple undirected graphs the results equal NetworkX's ``degree_histogram``,
``clustering``, ``average_clustering`` and connected component sizes.

``network_reporter`` wraps a statistic as a ``DataCollector`` model reporter that can be
checkpointed (no lambda)::

    DataCollector({"giant": network_reporter("contacts", largest_component)})
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from scipy.sparse import csr_matrix


def as_adjacency(graph: Any) -> csr_matrix:
    """The binary, symmetric, loop-free adjacency of ``graph`` as a CSR matrix."""
    from scipy import sparse  # noqa: PLC0415 - scipy is heavy

    if sparse.issparse(graph):
        matrix = sparse.csr_matrix(graph)
    elif hasattr(graph, "adjacency") and hasattr(graph, "_row"):
        matrix = graph.adjacency()
    elif hasattr(graph, "get_adjacency_sparse"):  # igraph
        matrix = sparse.csr_matrix(graph.get_adjacency_sparse())
    else:
        import networkx as nx  # noqa: PLC0415

        nx_graph = graph.G if hasattr(graph, "G") else graph
        matrix = nx.to_scipy_sparse_array(nx_graph, weight=None, format="csr")
    matrix = (matrix != 0).astype(np.int64)
    matrix = sparse.csr_matrix(((matrix + matrix.T) > 0).astype(np.int64))
    return _without_diagonal(matrix, sparse)


def _without_diagonal(matrix: csr_matrix, sparse: Any) -> csr_matrix:
    """``matrix`` without its diagonal and stored zeros, entries kept in their order."""
    matrix.sort_indices()
    counts = np.diff(matrix.indptr)
    rows = np.repeat(np.arange(matrix.shape[0], dtype=matrix.indices.dtype), counts)
    keep = (matrix.indices != rows) & (matrix.data != 0)
    indptr = np.zeros_like(matrix.indptr)
    np.cumsum(np.bincount(rows[keep], minlength=matrix.shape[0]), out=indptr[1:])
    return sparse.csr_matrix(
        (matrix.data[keep], matrix.indices[keep], indptr), shape=matrix.shape
    )


def degrees(graph: Any) -> np.ndarray:
    """The degree of every node, in node order."""
    return _degrees(as_adjacency(graph))


def _degrees(adjacency: csr_matrix) -> np.ndarray:
    """Row sums of a 0/1 adjacency without stored zeros: the row lengths, as int64."""
    return np.diff(adjacency.indptr).astype(np.int64)


def degree_distribution(graph: Any) -> np.ndarray:
    """``counts[k]`` = number of nodes of degree ``k``, as ``networkx.degree_histogram``."""
    return np.bincount(degrees(graph))


def clustering(graph: Any) -> np.ndarray:
    """The local clustering coefficient of every node, as ``networkx.clustering``."""
    adjacency = as_adjacency(graph)
    triangles = np.asarray(
        (adjacency @ adjacency).multiply(adjacency).sum(axis=1)
    ).ravel()
    k = _degrees(adjacency).astype(float)
    pairs = k * (k - 1)
    return np.divide(triangles, pairs, out=np.zeros_like(pairs), where=pairs > 0)


def average_clustering(graph: Any) -> float:
    """The mean local clustering over all nodes, as ``networkx.average_clustering``."""
    values = clustering(graph)
    return float(values.mean()) if values.size else 0.0


def component_sizes(graph: Any) -> np.ndarray:
    """The sizes of the connected components, largest first."""
    from scipy.sparse.csgraph import connected_components  # noqa: PLC0415

    adjacency = as_adjacency(graph)
    if adjacency.shape[0] == 0:
        return np.zeros(0, dtype=np.int64)
    _, labels = connected_components(adjacency, directed=False)
    return np.sort(np.bincount(labels))[::-1]


def largest_component(graph: Any) -> int:
    """The number of nodes in the largest connected component."""
    sizes = component_sizes(graph)
    return int(sizes[0]) if sizes.size else 0


def mean_degree(graph: Any) -> float:
    """The mean degree."""
    values = degrees(graph)
    return float(values.mean()) if values.size else 0.0


def network_reporter(attribute: str, statistic: Callable[[Any], Any]) -> partial:
    """A model reporter computing ``statistic(getattr(model, attribute))``.

    Unlike a lambda it can be pickled, so models that use it can be checkpointed.

    Args:
        attribute: the model attribute holding the network.
        statistic: a module-level function of the network, such as ``mean_degree``.
    """
    return partial(_report, attribute=attribute, statistic=statistic)


def _report(model: Any, attribute: str, statistic: Callable[[Any], Any]) -> Any:
    return statistic(getattr(model, attribute))
