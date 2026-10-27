"""Run a reference model split across MPI ranks (a helper of ``test_mpi.py``).

``mpirun -n K python tests/distributed/mpi_run.py CASE STEPS OUT`` builds case
``CASE`` with ``K`` partitions, runs ``STEPS`` steps, and rank 0 writes the
reporter rows and the SHA-256 of every agent's state to the JSON file ``OUT``.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import sys
from pathlib import Path

from modelly import Model
from modelly.distributed import Cluster, partition
from modelly.examples.distributed.grid_epidemic import (
    SUSCEPTIBLE,
    EpidemicScenario,
    GridEpidemic,
    Person,
)
from modelly.examples.distributed.network_sir import NetworkScenario, NetworkSIR
from modelly.space import OrthogonalMooreGrid

SEED = 7
GRID_SIDE, GRID_PEOPLE = 24, 400
NETWORK_PEOPLE = 300


class Fragile(Person):
    """Person 0 fails in ``advance``: an error on the one rank that owns it."""

    def advance(self):
        """Fail for person 0 only."""
        if self.key == 0:
            raise RuntimeError("person 1 cannot advance")
        super().advance()


class FragileEpidemic(GridEpidemic):
    """The grid epidemic with one fragile person."""

    def __init__(self, scenario=EpidemicScenario):
        """A torus with fragile people at random cells."""
        Model.__init__(self, scenario=scenario)
        s = self.scenario
        self.grid = OrthogonalMooreGrid(
            (s.width, s.height), torus=True, random=self.random
        )
        cells = list(self.grid.all_cells)
        picks = self.rng.integers(0, len(cells), size=s.people).tolist()
        for key, pick in enumerate(picks):
            Fragile(self, cells[pick], SUSCEPTIBLE, key)


# How each case is split into k parts: grid blocks of one row, or a graph cut.
FAILING = {
    "failing": lambda k: (
        FragileEpidemic,
        EpidemicScenario(
            rng=SEED, width=GRID_SIDE, height=GRID_SIDE, people=GRID_PEOPLE
        ),
        partition.grid_blocks(1, k),
    )
}
CASES = {
    "grid": lambda k: (
        GridEpidemic,
        EpidemicScenario(
            rng=SEED, width=GRID_SIDE, height=GRID_SIDE, people=GRID_PEOPLE
        ),
        partition.grid_blocks(1, k),
    ),
    "network": lambda k: (
        NetworkSIR,
        NetworkScenario(rng=SEED, people=NETWORK_PEOPLE),
        partition.graph(k),
    ),
}


def digest(states: list[tuple]) -> str:
    """One SHA-256 over the agents' states, in stream-key order."""
    return hashlib.sha256(pickle.dumps(states, protocol=4)).hexdigest()


def main(case: str, steps: int, out: str) -> None:
    """Run ``case`` on every rank; rank 0 writes the outputs."""
    from mpi4py import MPI  # noqa: PLC0415 - only under mpirun

    model_class, scenario, split = (CASES | FAILING)[case](MPI.COMM_WORLD.Get_size())
    with Cluster(backend="mpi") as cluster:
        model = cluster.build(model_class, scenario, split)
        model.run_for(steps)
        rows = model.collect().to_dict(orient="list")
        states = digest(model.states())
        if cluster.is_root:
            payload = json.dumps({"rows": rows, "states": states})
            Path(out).write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3])
