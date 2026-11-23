# Networks: dynamic and multilayer

Contact structures change over time and have several layers at once: the same people meet
at home, at school and at work. `modelly.space.networks` models both, on numpy and scipy only.
For a static network whose nodes are cells that agents move between, use the `Network` cell
space; the structures here are for who-meets-whom.

Nodes are any hashable labels, or a count `n` for labels `0 .. n-1`. Every node has a row, in
the order nodes were added, so the adjacency is a sparse matrix whose rows line up with
per-node numpy arrays: an infection state, an agent column.

## Temporal networks

A `TemporalNetwork` edge is active on `start <= time < end`:

```python
import math

from modelly import Model
from modelly.space.networks import TemporalNetwork

model = Model(rng=1)
contacts = TemporalNetwork(clock=model)  # queries follow model.time
contacts.add_edge("ann", "bob", (0, 8))  # meet during the first eight steps
contacts.add_edge("bob", "cy", (3, math.inf), weight=2.0)  # from step three on
contacts.neighbors("bob")  # at model.time
```

The network keeps the pending activations and expirations in two heaps, so moving time forward
touches only the edges that change: O(changed edges), not O(edges). Without a clock, call
`contacts.advance_to(time)`, which returns the number of edges switched. Moving time backward
replays every edge from the start. Neighbour queries (`neighbors`, `weighted_neighbors`,
`degree`, `has_edge`) cost O(degree); `adjacency()` is the active network as a CSR matrix,
rebuilt only after a change. Edge-list files with `start` and `end` columns load with
`read_temporal_edge_list`.

## Multilayer networks

```python
from modelly.space.networks import MultilayerNetwork

network = MultilayerNetwork(n_people, {"household": 1.0, "school": 0.5, "work": 0.25})
network.add_edge(0, 1, "household")
network.add_edges(classmates, "school")

network.neighbors(4, "school")  # one layer
network.neighbors(4)  # any layer
# {node: layer weight x edge weight}
network.weighted_neighbors(4, ["household", "work"])
pressure = network.adjacency() @ infected  # all layers, weighted, one sparse product
# close the schools: the edges stay, the weight is zero
network.add_layer("school", 0.0)
```

Adding or removing an edge costs O(1). Each layer's matrix is cached and rebuilt, from that
layer's edges only, the first time `adjacency` is called after the layer changed.

## Contact matrices

`contact_matrix(network, groups)` gives `C[a, b]`, the mean contact weight a member of group
`a` has with members of group `b`, from the network's (weighted) adjacency, optionally for some
layers only. `age_groups(ages, [18, 65])` turns ages into groups: children, adults, seniors.
For an undirected network `N[a] C[a, b] = N[b] C[b, a]`.

```python
from modelly.space.networks import age_groups, contact_matrix

groups = age_groups(ages, [5, 18, 30, 50, 65])
household = contact_matrix(network, groups, layer="household")
everything = contact_matrix(network, groups)
```

## Import and export

| From | Call |
|---|---|
| NetworkX graph | `from_networkx(graph, layer_attribute="layer", weight="weight")` |
| igraph graph (if igraph is installed) | `from_igraph(graph, layer_attribute="layer")` |
| CSV `source,target[,layer][,weight]` | `read_edge_list(path)`; `write_edge_list(network, path)` |
| CSV `source,target,start[,end][,weight]` | `read_temporal_edge_list(path, clock=model)` |

CSV files are read and written as UTF-8 on every platform. Node labels read from a file are
strings.

## Network statistics as reporters

`degree_distribution`, `degrees`, `mean_degree`, `clustering`, `average_clustering`,
`component_sizes` and `largest_component` take a `MultilayerNetwork`, a `TemporalNetwork`, a
`Network` space, a NetworkX or igraph graph, or a scipy sparse matrix. They read the structure
as a simple undirected graph and cost a few sparse products, so they are cheap enough to
collect every step. On simple undirected graphs they equal NetworkX's `degree_histogram`,
`clustering`, `average_clustering` and connected component sizes (the tests check it).

`network_reporter(attribute, statistic)` makes a `DataCollector` model reporter that, unlike a
lambda, can be checkpointed:

```python
from modelly import DataCollector
from modelly.space.networks import largest_component, mean_degree, network_reporter

model.datacollector = DataCollector(
    {
        "mean_contacts": network_reporter("network", mean_degree),
        "giant": network_reporter("network", largest_component),
    }
)
```

## Checkpoints

Both network types are plain Python data and are saved and loaded with the model; a temporal
network's clock is restored as the loaded model. Cached matrices are rebuilt when needed.

## Example

[Layered Epidemic](https://github.com/RemiPelloux/Modelly/tree/main/modelly/examples/spatial/layered_epidemic)
runs an age-structured SIR epidemic on household, school and work layers and closes the schools
when prevalence crosses a threshold. The [API reference](apis/networks.md) lists every class and
function.
