"""Where does Mesa's virus example diverge from its migrated copy? A trace-level comparison.

    python paper/scripts/virus_trace.py --seeds 20          # data/virus_trace.json

Section 5.1 reports a small, consistent difference between Mesa 3.5's virus-on-network
example and the same code migrated to Modelly (fewer resistant, more susceptible nodes).
This script runs both in one process on the same seeds and compares them level by level:

1. the graph: built by ``nx.erdos_renyi_graph`` from the global streams, which the harness
   seeds before construction; the two arms must get the same edge set
2. the agents: one per node, in the same node order, with the same neighbourhoods
3. the initial outbreak: which nodes ``self.random.sample`` infects
4. the dynamics with the random streams aligned: after construction, both models' infected
   sets are made equal and both ``model.random`` generators reseeded to the same value, so
   that every later draw comes from the same stream; the per-node state vector is compared
   after every step, and at the first step that differs, the shuffled activation order and
   every draw of that step are compared agent by agent
5. the data collection: the reporters against a direct count of the states

What differs is the finding; the script reports it per level and per seed.
"""

from __future__ import annotations

import argparse
import importlib
import json
import random
import sys
from pathlib import Path

import numpy as np

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent
EXAMPLES = ROOT / "benchmarks" / "mesa_examples"
sys.path.insert(0, str(EXAMPLES))
sys.path.insert(0, str(PAPER / "scripts"))

from environment import environment  # noqa: E402

NODES, STEPS, ALIGN_SEED = 1000, 200, 777


def build(arm: str, seed: int, nodes: int):
    """One arm's model on ``seed``, the global streams seeded as the harness does."""
    random.seed(seed)
    np.random.seed(seed)
    module = importlib.import_module(f"virus_on_network.{arm}.model")
    return module, module.VirusOnNetwork(rng=seed, num_nodes=nodes)


def edges(model) -> set[tuple[int, int]]:
    """The graph's edge set."""
    return {tuple(sorted(e)) for e in model.grid.G.edges}


def states(model) -> dict[int, int]:
    """Node -> state value, read from the agents through their cells."""
    return {
        cell.coordinate: agent.state.value
        for cell in model.grid.all_cells
        for agent in cell.agents
    }


def neighbourhoods(model) -> dict[int, tuple[int, ...]]:
    """Node -> sorted neighbour nodes, as the agents see them."""
    return {
        cell.coordinate: tuple(sorted(c.coordinate for c in cell.neighborhood))
        for cell in model.grid.all_cells
    }


def agent_nodes(model) -> list[int]:
    """The agents' nodes in the order of ``model.agents``."""
    return [agent.cell.coordinate for agent in model.agents]


class Recorder:
    """Wraps ``random.random`` to log every draw with the agent that made it."""

    def __init__(self, generator) -> None:
        """Wrap ``generator``; the log starts empty."""
        self.generator = generator
        self.log: list[tuple[int | None, float]] = []
        self.current: int | None = None

    def random(self) -> float:
        """One draw, logged with the current agent."""
        value = self.generator.random()
        self.log.append((self.current, value))
        return value

    def __getattr__(self, name):
        """Every other method is the generator's."""
        return getattr(self.generator, name)


def align(model, module, infected: set[int], seed: int = ALIGN_SEED) -> None:
    """Set the infected nodes to ``infected`` and reseed the model's generator."""
    for cell in model.grid.all_cells:
        for agent in cell.agents:
            agent.state = (
                module.State.INFECTED
                if cell.coordinate in infected
                else module.State.SUSCEPTIBLE
            )
    model.random.seed(seed)


def mesa_derivation(model, module, seed: int) -> None:
    """Redo the outbreak as Mesa's constructor does it, from ``random.Random(seed)``.

    Mesa seeds ``model.random`` with the seed itself; Modelly with a 32-bit value derived
    from it. Reseeding both with the seed and redrawing the outbreak gives the migrated
    copy Mesa's exact stream, so a whole run can be compared bit for bit.
    """
    for cell in model.grid.all_cells:
        for agent in cell.agents:
            agent.state = module.State.SUSCEPTIBLE
    model.random.seed(seed)
    chosen = model.random.sample(
        list(model.grid.all_cells), model.initial_outbreak_size
    )
    for cell in chosen:
        for agent in cell.agents:
            agent.state = module.State.INFECTED
    model.datacollector = type(model.datacollector)(
        {
            "Infected": module.number_infected,
            "Susceptible": module.number_susceptible,
            "Resistant": module.number_resistant,
        }
    )
    model.datacollector.collect(model)


def stepped_states(
    model, module, record: Recorder | None = None
) -> tuple[dict, list[int]]:
    """One step; the states after it and the activation order (nodes), draws logged."""
    order: list[int] = []
    original_step = module.VirusAgent.step

    def traced_step(agent):
        order.append(agent.cell.coordinate)
        if record is not None:
            record.current = agent.cell.coordinate
        original_step(agent)

    module.VirusAgent.step = traced_step
    try:
        model.step()
    finally:
        module.VirusAgent.step = original_step
    return states(model), order


def reporters(model) -> dict[str, float]:
    """The data collector's last row."""
    frame = model.datacollector.get_model_vars_dataframe()
    return {k: float(v) for k, v in frame.iloc[-1].items()}


def compare(seed: int, nodes: int, steps: int) -> dict:
    """The five levels on one seed."""
    mesa_module, mesa = build("original", seed, nodes)
    modelly_module, modelly = build("migrated", seed, nodes)
    out: dict = {"seed": seed}
    out["same_graph"] = edges(mesa) == edges(modelly)
    out["same_agent_order"] = agent_nodes(mesa) == agent_nodes(modelly)
    out["same_neighbourhoods"] = neighbourhoods(mesa) == neighbourhoods(modelly)
    mesa_infected = {n for n, s in states(mesa).items() if s == 1}
    modelly_infected = {n for n, s in states(modelly).items() if s == 1}
    out["same_initial_outbreak"] = mesa_infected == modelly_infected
    out["initial_outbreak"] = {
        "mesa": sorted(mesa_infected),
        "modelly": sorted(modelly_infected),
    }
    # the dynamics with aligned streams
    align(mesa, mesa_module, mesa_infected)
    align(modelly, modelly_module, mesa_infected)
    first_divergence = None
    for step in range(1, steps + 1):
        a, _ = stepped_states(mesa, mesa_module)
        b, _ = stepped_states(modelly, modelly_module)
        if a != b:
            first_divergence = step
            break
    out["aligned_identical_steps"] = (
        steps if first_divergence is None else first_divergence - 1
    )
    out["first_divergence_step"] = first_divergence
    # the whole run, outbreak included, with Mesa's own seed derivation on both arms
    mesa_module, mesa = build("original", seed, nodes)
    modelly_module, modelly = build("migrated", seed, nodes)
    mesa_derivation(mesa, mesa_module, seed)
    mesa_derivation(modelly, modelly_module, seed)
    identical = states(mesa) == states(modelly)
    for _ in range(steps):
        mesa.step()
        modelly.step()
        identical = identical and states(mesa) == states(modelly)
    frames = (
        mesa.datacollector.get_model_vars_dataframe(),
        modelly.datacollector.get_model_vars_dataframe(),
    )
    out["same_run_with_mesa_seed_derivation"] = bool(
        identical
        and frames[0].reset_index(drop=True).equals(frames[1].reset_index(drop=True))
    )
    if first_divergence is not None:
        # replay to the step before, then trace that step on both
        mesa_module, mesa = build("original", seed, nodes)
        modelly_module, modelly = build("migrated", seed, nodes)
        align(mesa, mesa_module, mesa_infected)
        align(modelly, modelly_module, mesa_infected)
        for _ in range(first_divergence - 1):
            mesa.step()
            modelly.step()
        rec_a, rec_b = Recorder(mesa.random), Recorder(modelly.random)
        mesa.random, modelly.random = rec_a, rec_b
        before = states(mesa)
        a, order_a = stepped_states(mesa, mesa_module, rec_a)
        b, order_b = stepped_states(modelly, modelly_module, rec_b)
        changed = sorted(n for n in a if a[n] != b[n])
        out["divergence"] = {
            "same_activation_order": order_a == order_b,
            "first_order_difference": next(
                (i for i, (x, y) in enumerate(zip(order_a, order_b)) if x != y), None
            ),
            "draws": {"mesa": len(rec_a.log), "modelly": len(rec_b.log)},
            "first_draw_difference": next(
                (i for i, (x, y) in enumerate(zip(rec_a.log, rec_b.log)) if x != y),
                None,
            ),
            "nodes_differing_after_step": changed[:20],
            "states_before": {n: before[n] for n in changed[:20]},
            "mesa_after": {n: a[n] for n in changed[:20]},
            "modelly_after": {n: b[n] for n in changed[:20]},
        }
    # the reporters against a direct count, at the end of an unaligned run
    mesa_module, mesa = build("original", seed, nodes)
    modelly_module, modelly = build("migrated", seed, nodes)
    for _ in range(steps):
        mesa.step()
        modelly.step()
    counts = {}
    for name, model in (("mesa", mesa), ("modelly", modelly)):
        values = list(states(model).values())
        direct = {
            "Susceptible": values.count(0),
            "Infected": values.count(1),
            "Resistant": values.count(2),
        }
        reported = reporters(model)
        counts[name] = {
            "direct": direct,
            "reported": {k: reported[k] for k in direct},
            "agents": len(model.agents),
            "rows_collected": len(model.datacollector.get_model_vars_dataframe()),
        }
    out["reporters_match_direct_count"] = all(
        counts[n]["direct"] == {k: int(v) for k, v in counts[n]["reported"].items()}
        for n in counts
    )
    out["counts"] = counts
    return out


def main() -> None:
    """Run the comparison on the seeds and write the data file."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--seed-base", type=int, default=2000)
    parser.add_argument("--nodes", type=int, default=NODES)
    parser.add_argument("--steps", type=int, default=STEPS)
    options = parser.parse_args()
    rows = [
        compare(seed, options.nodes, options.steps)
        for seed in range(options.seed_base, options.seed_base + options.seeds)
    ]
    out = {
        "environment": environment(),
        "nodes": options.nodes,
        "steps": options.steps,
        "align_seed": ALIGN_SEED,
        "runs": rows,
    }
    (PAPER / "data" / "virus_trace.json").write_text(json.dumps(out, indent=1) + "\n")
    for key in (
        "same_graph",
        "same_agent_order",
        "same_neighbourhoods",
        "same_initial_outbreak",
        "same_run_with_mesa_seed_derivation",
        "reporters_match_direct_count",
    ):
        print(f"{key:30s} {sum(r[key] for r in rows)}/{len(rows)} seeds")
    print(
        "aligned streams: identical steps per seed:",
        [r["aligned_identical_steps"] for r in rows],
    )
    for r in rows:
        if r.get("divergence"):
            print(
                f"seed {r['seed']}: step {r['first_divergence_step']}:",
                json.dumps(r["divergence"])[:600],
            )
            break


if __name__ == "__main__":
    main()
