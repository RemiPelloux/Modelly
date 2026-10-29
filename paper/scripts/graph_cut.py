"""The graph partitioner's edge cut on a lattice, as the paper quotes it: data/graph_cut.json.

    python paper/scripts/graph_cut.py

Cuts a 30 x 30 lattice into four parts with ``modelly.distributed.partition.graph`` and
records the edges cut against the best split (two straight cuts, 60 edges) and against
a uniformly random assignment, the comparison ``tests/distributed/test_graphs.py`` makes.
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import numpy as np
from environment import environment

from modelly.distributed import partition

PAPER = Path(__file__).resolve().parents[1]
SIDE, PARTS, RANDOM_SEED = 30, 4, 0
OPTIMAL = 2 * SIDE  # two straight cuts across the lattice


def main() -> None:
    """Partition the lattice, compare the cut and write data/graph_cut.json."""
    graph = nx.grid_2d_graph(SIDE, SIDE)
    layout = partition.graph(PARTS).layout(graph)
    random_parts = np.random.default_rng(RANDOM_SEED).integers(
        0, PARTS, graph.number_of_nodes()
    )
    random_layout = type(layout)(
        layout.nodes, random_parts, layout._indptr, layout._indices
    )
    out = {
        "lattice": [SIDE, SIDE],
        "parts": PARTS,
        "edges": graph.number_of_edges(),
        "cut": int(layout.cut()),
        "optimal_cut": OPTIMAL,
        "cut_over_optimal": float(layout.cut() / OPTIMAL),
        "random_cut": int(random_layout.cut()),
        "part_sizes": [int(s) for s in layout.sizes()],
        "environment": environment(),
    }
    (PAPER / "data" / "graph_cut.json").write_text(json.dumps(out, indent=1) + "\n")
    print(
        json.dumps(
            {
                k: out[k]
                for k in ("cut", "optimal_cut", "cut_over_optimal", "random_cut")
            }
        )
    )


if __name__ == "__main__":
    main()
