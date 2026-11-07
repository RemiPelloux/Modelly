# Networks

`modelly.space.networks` holds the temporal and multilayer networks, contact matrices, network statistics and importers. It needs only numpy and scipy; NetworkX and igraph are used only to convert from their graphs. The guide is [Networks](https://remipelloux.github.io/Modelly/dev/networks.html). The static network cell space, `Network`, is on the [Space](https://remipelloux.github.io/Modelly/dev/apis/space.html#network) page.

Module

Contents

modelly.space.networks.temporal

TemporalNetwork, TemporalEdge

modelly.space.networks.multilayer

MultilayerNetwork

modelly.space.networks.contacts

contact_matrix, age_groups

modelly.space.networks.collectors

degree distribution, clustering, components, network_reporter

modelly.space.networks.io

NetworkX, igraph and edge-list CSV import and export

modelly.space.networks.base

node rows shared by both network types

## Temporal networks

Temporal networks: edges that exist during an interval of model time.

Every edge has an activation time `start` and an end time `end` and is active on `start <= time < end`. The network keeps two heaps of pending changes, so moving the clock forward with `advance_to` touches only the edges that switch on or off in between: O(changed edges x log edges). Neighbour queries read the active adjacency, O(degree). Given a `clock` (anything with a `time`, usually the model), every query first advances to `clock.time`, so the answers are always those of the current time.

Moving the clock backwards (a rewind) replays every edge from the start: O(edges).

#### `class TemporalEdge(u: int, v: int, start: float, end: float, weight: float)`

One edge with its lifetime, between node rows `u` and `v`.

Create new instance of TemporalEdge(u, v, start, end, weight)

#### `u: int`

Alias for field number 0

#### `v: int`

Alias for field number 1

#### `start: float`

Alias for field number 2

#### `end: float`

Alias for field number 3

#### `weight: float`

Alias for field number 4

#### `class TemporalNetwork(nodes: int | Iterable[Hashable] = 0, directed: bool = False, clock: Any = None)`

Edges with lifetimes, queried at the current time.

**Variables:**

- **nodes** – the node labels, in row order.
- **time** – the time the active edges correspond to.
- **clock** – an object with a `time` attribute that queries follow, or `None`.

Create an empty temporal network.

**Parameters:**

- **nodes** – a count (labels `0 .. n-1`) or the node labels; more are added by edges.
- **directed** – whether edges are one-way.
- **clock** – an object with a `time` attribute (a `Model`) queries advance to.

#### `add_edge(u: Hashable, v: Hashable, interval: tuple[float, float] = (-inf, inf), weight: float = 1.0) → int`

Add an edge active on `start <= time < end`, and return its id.

**Parameters:**

- **u** – one end (added as a node if new).
- **v** – the other end.
- **interval** – `(start, end)`; the default is always active.
- **weight** – the edge weight.

#### `remove_edge(edge_id: int) → None`

Remove an edge, active or not; pending changes for it are dropped lazily.

#### `advance_to(time: float) → int`

Make the active edges those of `time`; return how many edges changed.

#### `neighbors(node: Hashable) → list`

The nodes linked to `node` by an active edge.

#### `weighted_neighbors(node: Hashable) → dict`

Neighbour label to the summed weight of the active edges to it.

#### `degree(node: Hashable) → int`

The number of distinct active neighbours of `node`.

#### `has_edge(u: Hashable, v: Hashable) → bool`

Whether an active edge links `u` to `v`.

#### `active_edges() → Iterator[tuple[Any, Any, float]]`

`(u, v, weight)` for every active edge.

#### `number_of_active_edges() → int`

The number of active edges.

#### `adjacency() → csr_matrix`

The active adjacency (summed weights) as a CSR matrix, rows in `nodes` order.

## Multilayer networks

Multilayer networks: one set of nodes, several layers of weighted edges.

A contact network for an epidemic is the classic case: the same people are linked in a household layer, a school layer and a work layer, each with its own edges and its own weight (how much a contact on that layer counts). Queries take one layer, several, or all of them combined, with `combined weight = sum(layer weight * edge weight)`.

Edges are kept per layer in dictionaries of rows, so `add_edge` and `remove_edge` cost O(1) and `neighbors` costs O(degree). `adjacency` returns the sparse matrix for vectorised steps (`adjacency() @ infected`); it is cached per layer and rebuilt, in O(edges of that layer), on the first call after the layer changed.

#### `class MultilayerNetwork(nodes: int | Iterable[Hashable], layers: Mapping[str, float] | Iterable[str] = (), directed: bool = False)`

Nodes linked on named layers, each layer with a weight.

**Variables:**

- **nodes** – the node labels, in row order.
- **layer_weights** – layer name to its weight in combined queries.
- **directed** – whether an edge `u -> v` leaves `v -> u` absent.

Create a network over `nodes`.

**Parameters:**

- **nodes** – a count (labels `0 .. n-1`) or the node labels.
- **layers** – layer names, or a mapping of layer name to weight (default 1).
- **directed** – whether edges are one-way.

#### `property layers: list[str]`

The layer names, in the order they were added.

#### `add_layer(name: str, weight: float = 1.0) → None`

Add an empty layer, or change the weight of an existing one.

#### `add_edge(u: Hashable, v: Hashable, layer: str, weight: float = 1.0) → None`

Link `u` and `v` on `layer` (created if new); new nodes are added.

#### `add_edges(pairs: Iterable[tuple[Hashable, Hashable]], layer: str, weight: float = 1.0) → None`

Link every `(u, v)` of `pairs` on `layer` with the same `weight`.

#### `remove_edge(u: Hashable, v: Hashable, layer: str) → None`

Remove the edge between `u` and `v` on `layer`.

#### `has_edge(u: Hashable, v: Hashable, layer: str | None = None) → bool`

Whether `u` and `v` are linked on `layer`, or on any layer.

#### `neighbors(node: Hashable, layer: str | Sequence[str] | None = None) → list`

The nodes linked to `node` on the selected layers (all by default).

#### `weighted_neighbors(node: Hashable, layer: str | Sequence[str] | None = None) → dict`

Neighbour label to combined weight, `sum(layer weight * edge weight)`.

#### `degree(node: Hashable, layer: str | Sequence[str] | None = None) → int`

The number of distinct neighbours of `node` on the selected layers.

#### `edges(layer: str) → Iterator[tuple[Any, Any, float]]`

`(u, v, weight)` for every edge of `layer` (each undirected edge once).

#### `number_of_edges(layer: str | Sequence[str] | None = None) → int`

The number of edges on the selected layers, counted per layer.

#### `adjacency(layer: LayerSelection = None) → csr_matrix`

The combined weighted adjacency of the selected layers, rows in `nodes` order.

#### `to_networkx(layer: str | Sequence[str] | None = None) → Any`

A NetworkX graph of the selected layers, with the combined `weight` on edges.

## Contact matrices

Contact matrices: mean contacts between groups (age bands), for epidemic models.

#### `age_groups(ages: Sequence[float], breaks: Sequence[float]) → ndarray`

The group of every age: `0` below `breaks[0]`, `i` in `[breaks[i-1], breaks[i])`.

`age_groups(ages, [18, 65])` gives `0` for children, `1` for adults and `2` for people aged 65 and over.

#### `contact_matrix(network: Any, groups: Sequence[int], layer: str | Sequence[str] | None = None, n_groups: int | None = None) → ndarray`

Mean contacts a member of group `a` has with members of group `b`.

`C[a, b] = W(a, b) / N(a)`, where `W(a, b)` is the total weight of the edges from members of `a` to members of `b` and `N(a)` the size of group `a`; rows of empty groups are zero. For an undirected network `N(a) C[a, b] = N(b) C[b, a]`.

**Parameters:**

- **network** – a `MultilayerNetwork` or `TemporalNetwork`, or a sparse adjacency.
- **groups** – the group (`0 .. n_groups-1`) of every node, in row order.
- **layer** – for a multilayer network, the layer or layers to count (all by default), combined with their layer weights.
- **n_groups** – the number of groups; defaults to `max(groups) + 1`.

## Network statistics

Cheap network statistics for data collection: degrees, clustering, components.

Every statistic takes a graph in any of the forms a model holds: a `MultilayerNetwork` or `TemporalNetwork` (its current combined adjacency), a `Network` cell space, a NetworkX graph, an igraph graph or a scipy sparse matrix. The structure is read as a simple undirected graph (weights, edge directions and self-loops are ignored), and the work is a few sparse-matrix products, so a reporter costs milliseconds on large graphs. On simple undirected graphs the results equal NetworkX’s `degree_histogram`, `clustering`, `average_clustering` and connected component sizes.

`network_reporter` wraps a statistic as a `DataCollector` model reporter that can be checkpointed (no lambda):

```default
DataCollector({"giant": network_reporter("contacts", largest_component)})
```

#### `as_adjacency(graph: Any) → csr_matrix`

The binary, symmetric, loop-free adjacency of `graph` as a CSR matrix.

#### `degrees(graph: Any) → ndarray`

The degree of every node, in node order.

#### `degree_distribution(graph: Any) → ndarray`

`counts[k]` = number of nodes of degree `k`, as `networkx.degree_histogram`.

#### `clustering(graph: Any) → ndarray`

The local clustering coefficient of every node, as `networkx.clustering`.

#### `average_clustering(graph: Any) → float`

The mean local clustering over all nodes, as `networkx.average_clustering`.

#### `component_sizes(graph: Any) → ndarray`

The sizes of the connected components, largest first.

#### `largest_component(graph: Any) → int`

The number of nodes in the largest connected component.

#### `mean_degree(graph: Any) → float`

The mean degree.

#### `network_reporter(attribute: str, statistic: Callable[[Any], Any]) → partial`

A model reporter computing `statistic(getattr(model, attribute))`.

Unlike a lambda it can be pickled, so models that use it can be checkpointed.

**Parameters:**

- **attribute** – the model attribute holding the network.
- **statistic** – a module-level function of the network, such as `mean_degree`.

## Import and export

Networks from NetworkX, igraph and edge-list CSV files, and back to CSV.

Edge lists are CSV files with a header. Multilayer files have `source` and `target` columns and optional `layer` and `weight` columns; temporal files add `start` and an optional `end`. Files are read and written as UTF-8 on every platform; node labels read from a file are strings.

#### `from_networkx(graph: Any, layer_attribute: str | None = None, weight: str = 'weight') → MultilayerNetwork`

A `MultilayerNetwork` with the nodes and edges of a NetworkX graph.

**Parameters:**

- **graph** – any NetworkX graph; a directed graph gives a directed network.
- **layer_attribute** – the edge attribute naming each edge’s layer; without it, or for edges lacking it, edges go to layer `"default"`.
- **weight** – the edge attribute holding the weight (1 when missing).

#### `from_igraph(graph: Any, layer_attribute: str | None = None, weight: str = 'weight') → MultilayerNetwork`

A `MultilayerNetwork` from an igraph graph (igraph is optional, not a dependency).

Nodes are labelled by the vertex attribute `name` when present, else by index.

#### `read_edge_list(path: str | Path, directed: bool = False) → MultilayerNetwork`

A `MultilayerNetwork` from a CSV edge list (`source,target[,layer][,weight]`).

#### `write_edge_list(network: MultilayerNetwork, path: str | Path) → Path`

Write every edge of every layer as `source,target,layer,weight` (UTF-8 CSV).

#### `read_temporal_edge_list(path: str | Path, directed: bool = False, clock: Any = None) → TemporalNetwork`

A `TemporalNetwork` from a CSV edge list (`source,target,start[,end][,weight]`).

A missing or empty `end` means the edge never ends.

Node rows shared by the temporal and multilayer networks.

Nodes are any hashable labels; each gets an integer row, in insertion order, so the network’s adjacency is a sparse matrix whose rows line up with a per-node numpy vector (an agent column, a state array). Edges live in dictionaries keyed by rows, so adding or removing one edge costs O(1) and a neighbour query costs O(degree).

#### `class NodeRows`

Labels to rows and back, for a network over `nodes`.

#### `add_node(node: Hashable) → int`

Add `node` if it is new, and return its row.

#### `row(node: Hashable) → int`

The row of `node`.

#### `rows(nodes: Iterable[Hashable]) → ndarray`

The rows of `nodes`.

#### `csr_from_rows(rows: dict[int, dict[int, float]], n: int, scale: float = 1.0) → csr_matrix`

A CSR matrix with entry `scale * rows[i][j]` for every stored pair.
