"""Run one playbook variant and print its whole trajectory, not just its summary.

    python paper/scripts/trajectory_worker.py <playbook> <variant> <seed> <size> [steps]

Started by trajectories.py inside the framework's own virtual environment (as the
playbook harness does), so it must need nothing beyond numpy and the framework. It runs
the playbook's own ``build`` and ``simulate``, then reads what the model recorded step
by step and the spatial pattern it ends in:

grid_epidemic   the infected count at every step; which cells hold anyone ever infected
                at the end (a 0/1 layer, for the cluster sizes)
schelling       the share of happy residents and the number of moves at every step; the
                distribution of every resident's share of same-kind neighbours at the end
predator_prey   the sheep, wolf and bare-grass series at every step
"""

from __future__ import annotations

import importlib
import json
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "benchmarks" / "playbooks"
sys.path.insert(0, str(HARNESS))

from registry import PLAYBOOKS  # noqa: E402

BINS = 10  # histogram bins of the same-kind share, on [0, 1]


def grid_epidemic(model, variant: str, module, params: dict) -> dict:
    """The infected series and the layer of cells with anyone ever infected."""
    side, susceptible = params["side"], module.S
    layer = np.zeros((side, side), dtype=np.int64)
    if variant == "mesa":
        for agent in model.agents:
            if agent.state != susceptible:
                layer[agent.pos] += 1
    elif variant == "mesa3":
        for agent in model.agents:
            if agent.state != susceptible:
                layer[agent.cell.coordinate] += 1
    else:
        table = model.columns[module.Person]
        layer = model.index.to_layer(
            model.index.counts(table.row, table.state != susceptible)
        )
    return {
        "series": {"infected": [int(x) for x in model.infected_history]},
        "layer": (np.asarray(layer) > 0).astype(np.int8).ravel().tolist(),
        "side": side,
    }


def schelling(model, variant: str, module, params: dict) -> dict:
    """The happiness and moves series and the histogram of same-kind shares."""
    if variant in ("mesa", "mesa3"):
        shares = []
        for agent in model.agents:
            neighbours = agent.neighbours()
            if neighbours:
                same = sum(1 for other in neighbours if other.kind == agent.kind)
                shares.append(same / len(neighbours))
        shares = np.asarray(shares, dtype=float)
    else:
        similar, around = model.neighbours(model.columns[module.Resident])
        some = around > 0
        shares = similar[some] / around[some]
    histogram, _ = np.histogram(shares, bins=BINS, range=(0.0, 1.0))
    return {
        "series": {
            "happy": [float(h[0]) for h in model.history],
            "moves": [int(h[1]) for h in model.history],
        },
        "shares": histogram.tolist(),
        "residents": int(shares.shape[0]),
    }


def predator_prey(model, variant: str, module, params: dict) -> dict:
    """The three population series."""
    return {
        "series": {
            "sheep": [int(h[0]) for h in model.history],
            "wolves": [int(h[1]) for h in model.history],
            "grass": [float(h[2]) for h in model.history],
        }
    }


EXTRACT = {
    "grid_epidemic": grid_epidemic,
    "schelling": schelling,
    "predator_prey": predator_prey,
}


def main(argv: list[str]) -> int:
    """Run the variant once and print the RESULT line."""
    playbook, variant, seed, size = argv[0], argv[1], int(argv[2]), argv[3]
    spec = PLAYBOOKS[playbook]
    steps = int(argv[4]) if len(argv) > 4 else spec["steps"]
    module = importlib.import_module(f"{playbook}.{spec['variants'][variant]}")
    params = {**spec["params"], **spec["sizes"][size]}
    warnings.simplefilter("ignore")
    model = module.build(seed=seed, **params)
    result = module.simulate(model, steps)
    row = {
        "playbook": playbook,
        "variant": variant,
        "seed": seed,
        "size": size,
        "steps": steps,
        "stats": result["stats"],
        **EXTRACT[playbook](model, variant, module, params),
    }
    sys.stdout.write("RESULT " + json.dumps(row) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
