"""Networks from NetworkX, igraph and edge-list CSV files, and back to CSV.

Edge lists are CSV files with a header. Multilayer files have ``source`` and ``target``
columns and optional ``layer`` and ``weight`` columns; temporal files add ``start`` and
an optional ``end``. Files are read and written as UTF-8 on every platform; node labels
read from a file are strings.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from modelly.space.networks.multilayer import DEFAULT_WEIGHT, MultilayerNetwork
from modelly.space.networks.temporal import TemporalNetwork

DEFAULT_LAYER = "default"
SOURCE, TARGET, LAYER, WEIGHT, START, END = (
    "source",
    "target",
    "layer",
    "weight",
    "start",
    "end",
)


def from_networkx(
    graph: Any, layer_attribute: str | None = None, weight: str = WEIGHT
) -> MultilayerNetwork:
    """A ``MultilayerNetwork`` with the nodes and edges of a NetworkX graph.

    Args:
        graph: any NetworkX graph; a directed graph gives a directed network.
        layer_attribute: the edge attribute naming each edge's layer; without it, or for
            edges lacking it, edges go to layer ``"default"``.
        weight: the edge attribute holding the weight (1 when missing).
    """
    network = MultilayerNetwork(list(graph.nodes), directed=graph.is_directed())
    for u, v, data in graph.edges(data=True):
        layer = (
            data.get(layer_attribute, DEFAULT_LAYER)
            if layer_attribute
            else DEFAULT_LAYER
        )
        network.add_edge(u, v, str(layer), data.get(weight, DEFAULT_WEIGHT))
    return network


def from_igraph(
    graph: Any, layer_attribute: str | None = None, weight: str = WEIGHT
) -> MultilayerNetwork:
    """A ``MultilayerNetwork`` from an igraph graph (igraph is optional, not a dependency).

    Nodes are labelled by the vertex attribute ``name`` when present, else by index.
    """
    names = (
        graph.vs["name"]
        if "name" in graph.vs.attributes()
        else list(range(graph.vcount()))
    )
    network = MultilayerNetwork(names, directed=graph.is_directed())
    attributes = set(graph.es.attributes())
    for edge in graph.es:
        layer = (
            edge[layer_attribute]
            if layer_attribute and layer_attribute in attributes
            else DEFAULT_LAYER
        )
        w = edge[weight] if weight in attributes else DEFAULT_WEIGHT
        network.add_edge(names[edge.source], names[edge.target], str(layer), w)
    return network


def _rows(path: Path) -> Iterator[dict[str, str]]:
    """The rows of a CSV file with a header, read as UTF-8."""
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = {SOURCE, TARGET} - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path} lacks the column(s) {sorted(missing)}.")
        yield from reader


def read_edge_list(path: str | Path, directed: bool = False) -> MultilayerNetwork:
    """A ``MultilayerNetwork`` from a CSV edge list (``source,target[,layer][,weight]``)."""
    network = MultilayerNetwork(0, directed=directed)
    for row in _rows(Path(path)):
        layer = row.get(LAYER) or DEFAULT_LAYER
        weight = float(row.get(WEIGHT) or DEFAULT_WEIGHT)
        network.add_edge(row[SOURCE], row[TARGET], layer, weight)
    return network


def write_edge_list(network: MultilayerNetwork, path: str | Path) -> Path:
    """Write every edge of every layer as ``source,target,layer,weight`` (UTF-8 CSV)."""
    path = Path(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([SOURCE, TARGET, LAYER, WEIGHT])
        for layer in network.layers:
            for u, v, w in network.edges(layer):
                writer.writerow([u, v, layer, w])
    return path


def read_temporal_edge_list(
    path: str | Path, directed: bool = False, clock: Any = None
) -> TemporalNetwork:
    """A ``TemporalNetwork`` from a CSV edge list (``source,target,start[,end][,weight]``).

    A missing or empty ``end`` means the edge never ends.
    """
    network = TemporalNetwork(directed=directed, clock=clock)
    for row in _rows(Path(path)):
        start = float(row.get(START) or -math.inf)
        end = float(row.get(END) or math.inf)
        weight = float(row.get(WEIGHT) or DEFAULT_WEIGHT)
        network.add_edge(row[SOURCE], row[TARGET], (start, end), weight)
    return network
