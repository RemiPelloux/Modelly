"""Dynamic and multilayer networks, contact matrices and network statistics.

Pure Python on numpy and scipy; NetworkX and igraph are needed only to convert from
their graphs.

- ``TemporalNetwork``: edges with lifetimes, updated in O(changed edges) as time advances.
- ``MultilayerNetwork``: one set of nodes linked on named, weighted layers
  (household, school, work).
- ``contact_matrix``: mean contacts between groups, such as age bands.
- ``degree_distribution``, ``clustering``, ``component_sizes`` and friends: cheap
  statistics for data collection, wrapped by ``network_reporter``.
- ``from_networkx``, ``from_igraph``, ``read_edge_list``, ``write_edge_list``,
  ``read_temporal_edge_list``: import and export.
"""

from modelly.space.networks.collectors import (
    as_adjacency,
    average_clustering,
    clustering,
    component_sizes,
    degree_distribution,
    degrees,
    largest_component,
    mean_degree,
    network_reporter,
)
from modelly.space.networks.contacts import age_groups, contact_matrix
from modelly.space.networks.io import (
    from_igraph,
    from_networkx,
    read_edge_list,
    read_temporal_edge_list,
    write_edge_list,
)
from modelly.space.networks.multilayer import MultilayerNetwork
from modelly.space.networks.temporal import TemporalEdge, TemporalNetwork

__all__ = [
    "MultilayerNetwork",
    "TemporalEdge",
    "TemporalNetwork",
    "age_groups",
    "as_adjacency",
    "average_clustering",
    "clustering",
    "component_sizes",
    "contact_matrix",
    "degree_distribution",
    "degrees",
    "from_igraph",
    "from_networkx",
    "largest_component",
    "mean_degree",
    "network_reporter",
    "read_edge_list",
    "read_temporal_edge_list",
    "write_edge_list",
]
