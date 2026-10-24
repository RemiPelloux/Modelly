"""Contact matrices: mean contacts between groups (age bands), for epidemic models."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np


def age_groups(ages: Sequence[float], breaks: Sequence[float]) -> np.ndarray:
    """The group of every age: ``0`` below ``breaks[0]``, ``i`` in ``[breaks[i-1], breaks[i])``.

    ``age_groups(ages, [18, 65])`` gives ``0`` for children, ``1`` for adults and ``2``
    for people aged 65 and over.
    """
    return np.searchsorted(np.asarray(breaks), np.asarray(ages), side="right")


def contact_matrix(
    network: Any,
    groups: Sequence[int],
    layer: str | Sequence[str] | None = None,
    n_groups: int | None = None,
) -> np.ndarray:
    """Mean contacts a member of group ``a`` has with members of group ``b``.

    ``C[a, b] = W(a, b) / N(a)``, where ``W(a, b)`` is the total weight of the edges from
    members of ``a`` to members of ``b`` and ``N(a)`` the size of group ``a``; rows of empty
    groups are zero. For an undirected network ``N(a) C[a, b] = N(b) C[b, a]``.

    Args:
        network: a ``MultilayerNetwork`` or ``TemporalNetwork``, or a sparse adjacency.
        groups: the group (``0 .. n_groups-1``) of every node, in row order.
        layer: for a multilayer network, the layer or layers to count (all by default),
            combined with their layer weights.
        n_groups: the number of groups; defaults to ``max(groups) + 1``.
    """
    from scipy import sparse  # noqa: PLC0415 - scipy is heavy

    if sparse.issparse(network):
        adjacency = sparse.csr_matrix(network)
    elif layer is None:
        adjacency = network.adjacency()
    else:
        adjacency = network.adjacency(layer)
    groups = np.asarray(groups, dtype=np.intp)
    k = int(groups.max()) + 1 if n_groups is None else n_groups
    n = groups.shape[0]
    membership = sparse.csr_matrix((np.ones(n), (np.arange(n), groups)), shape=(n, k))
    totals = (membership.T @ adjacency @ membership).toarray()
    sizes = np.bincount(groups, minlength=k).astype(float)[:, np.newaxis]
    return np.divide(totals, sizes, out=np.zeros_like(totals), where=sizes > 0)
