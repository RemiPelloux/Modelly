"""Same code on both frameworks: Mesa's own bundled examples against their codemod ports.

    python benchmarks/mesa_examples/run.py --rounds 10 --seeds 100 --core 2
        # paper/data/mesa_examples.json

The models are written by Mesa's developers (copied unmodified from Mesa 3.5.1 into
``<example>/original``); ``<example>/port`` is the output of ``python -m modelly.migrate
--write`` plus the steps listed in this directory's README. Each round runs the original and
its port in fresh interpreters, alternating which goes first, pinned to one core, on the
round's seed, and records the CPU time of the steps (``time.process_time``) and the summary
statistics at the last step. The agreement mode runs both on shared seeds at the same size and
compares each statistic by a paired t-test, a Kolmogorov-Smirnov test and a TOST at half a
standard deviation, Holm-corrected over all comparisons (paper/scripts/agreement.py).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "playbooks"))
sys.path.insert(0, str(ROOT / "paper" / "scripts"))

from agreement import compare_one, holm  # noqa: E402
from environment import environment  # noqa: E402

PYTHON = ROOT / ".venv" / "bin" / "python"
OUTPUT = ROOT / "paper" / "data" / "mesa_examples.json"
ARMS = ("original", "port")
# Each model reporter at the last step and averaged over the run (populations can die out).
COLLECTED = (
    "{**{'final ' + k: v[-1] for k, v in model.datacollector.model_vars.items()}, "
    "**{'mean ' + k: numpy.mean(v) for k, v in model.datacollector.model_vars.items()}}"
)
POLARISATION = (
    "{'polarisation': float(numpy.linalg.norm(numpy.mean([a.direction / numpy.linalg.norm("
    "a.direction) for a in model.agents], axis=0))), "
    "'neighbours': float(numpy.mean([len(a.neighbors) for a in model.agents]))}"
)
# Mesa's default parameters unless noted in the README; ``smoke`` is for a quick check only.
EXAMPLES = {
    "conways_game_of_life": {
        "cls": "ConwaysGameOfLife", "params": {}, "steps": 100,
        "smoke": {"width": 20, "height": 20},
        "stats": "{'alive': sum(a.state == a.ALIVE for a in model.agents)}",
    },
    "pd_grid": {
        "cls": "PdGrid", "params": {}, "steps": 100,
        "smoke": {"width": 20, "height": 20}, "stats": COLLECTED,
    },
    "virus_on_network": {
        "cls": "VirusOnNetwork", "params": {"num_nodes": 1000}, "steps": 200,
        "smoke": {"num_nodes": 200}, "stats": COLLECTED,
    },
    "boid_flockers": {
        "cls": "BoidFlockers", "scenario": "BoidsScenario", "params": {}, "steps": 100,
        "smoke": {"population_size": 50}, "stats": POLARISATION,
    },
    "boltzmann_wealth_model": {
        "cls": "BoltzmannWealth", "scenario": "BoltzmannScenario",
        "params": {"n": 2500, "width": 50, "height": 50},
        "steps": 100, "smoke": {"n": 50}, "stats": COLLECTED,
    },
    "schelling": {
        "cls": "Schelling", "scenario": "SchellingScenario",
        "params": {"width": 50, "height": 50}, "steps": 50,
        "smoke": {"width": 10, "height": 10}, "stats": COLLECTED,
    },
    "wolf_sheep": {
        "cls": "WolfSheep", "scenario": "WolfSheepScenario", "steps": 100,
        "params": {"width": 50, "height": 50, "initial_sheep": 625, "initial_wolves": 312},
        "smoke": {"width": 10, "height": 10}, "stats": COLLECTED,
    },
    "epstein_civil_violence": {
        "cls": "EpsteinCivilViolence", "scenario": "EpsteinScenario", "params": {},
        "steps": 100, "smoke": {"width": 15, "height": 15}, "stats": COLLECTED,
    },
}  # fmt: skip
SEED_BASE = 2000
ONE_RUN = """
import gc, importlib, json, random, sys, time, warnings
import numpy
warnings.simplefilter("ignore")
base, name, arm, cls, seed, params, steps, stats, scenario = sys.argv[1:10]
seed, steps = int(seed), int(steps)
random.seed(seed); numpy.random.seed(seed)  # networkx draws from the global streams
sys.path.insert(0, base); module = importlib.import_module(name + "." + arm + ".model")
if scenario:  # Mesa 3.5's newer examples take their parameters as a Scenario
    setup = getattr(module, scenario)(rng=seed, **json.loads(params))
    model = getattr(module, cls)(scenario=setup)
else:
    model = getattr(module, cls)(rng=seed, **json.loads(params))
gc.collect(); start = time.process_time()
for _ in range(steps):
    model.step()
run = time.process_time() - start
print(json.dumps({"run": run, "stats": {k: float(v) for k, v in eval(stats).items()}}))
"""


def run(name: str, arm: str, seed: int, params: dict, core: str | None) -> dict:
    """One run of one arm in a fresh interpreter, pinned to ``core`` when given."""
    spec = EXAMPLES[name]
    command = [str(PYTHON), "-c", ONE_RUN, str(HERE), name, arm, spec["cls"], str(seed)]
    command += [json.dumps(params), str(spec["steps"]), spec["stats"]]
    command.append(spec.get("scenario", ""))
    if core is not None:
        command = ["taskset", "-c", core, *command]
    out = subprocess.run(command, capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def measure(name: str, params: dict, rounds: int, core: str) -> dict:
    """Paired rounds of one example: median times, ratio quartiles, identical statistics."""
    times, same = {arm: [] for arm in ARMS}, 0
    for seed in range(rounds):
        order = ARMS if seed % 2 == 0 else ARMS[::-1]
        out = {arm: run(name, arm, seed, params, core) for arm in order}
        for arm, result in out.items():
            times[arm].append(result["run"])
        same += out["original"]["stats"] == out["port"]["stats"]
    ratios = [p / o for o, p in zip(times["original"], times["port"], strict=True)]
    low, high = statistics.quantiles(ratios, n=4)[::2] if rounds > 1 else ratios * 2
    return {
        "original": statistics.median(times["original"]),
        "port": statistics.median(times["port"]),
        "ratio": statistics.median(ratios), "lq": low, "uq": high,
        "min": min(ratios), "max": max(ratios), "identical_rounds": same,
        "rounds": rounds, "times": times,
    }  # fmt: skip


def collect(name: str, params: dict, seeds: int, jobs: int, core: str | None) -> list:
    """The statistics of both arms on seeds ``SEED_BASE`` and up, as (original, port) pairs."""

    def both(seed: int) -> tuple[dict, dict]:
        return tuple(run(name, arm, seed, params, core)["stats"] for arm in ARMS)

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(both, range(SEED_BASE, SEED_BASE + seeds)))


def agree(name: str, pairs: list) -> list[dict]:
    """Each statistic of the port against the original over the shared seeds."""
    rows = []
    for stat in pairs[0][0]:
        a = [o[stat] for o, _ in pairs]
        b = [p[stat] for _, p in pairs]
        if not all(math.isfinite(x) for x in a + b):
            rows.append({"example": name, "stat": stat, "skipped": "non-finite values"})
            continue
        rows.append({"example": name, "stat": stat} | compare_one(a, b))
    return rows


def adjust(rows: list[dict]) -> None:
    """Holm-adjusted p-values over every compared statistic, in place."""
    tested = [r for r in rows if "skipped" not in r]
    for key in ("paired", "ks", "tost"):
        for row, p in zip(tested, holm([r[key] for r in tested]), strict=True):
            row[f"{key}_holm"] = p


def parse() -> argparse.Namespace:
    """The command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--seeds", type=int, default=100, help="0 skips the agreement")
    parser.add_argument("--core", default="2", help="taskset CPU list for the timings")
    parser.add_argument("--jobs", type=int, default=4, help="parallel agreement runs")
    parser.add_argument("--agree-cores", help="taskset CPU list for the agreement runs")
    parser.add_argument("--smoke", action="store_true", help="small sizes, quick check")
    parser.add_argument("--only", nargs="*", default=list(EXAMPLES))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser.parse_args()


def example(name: str, options: argparse.Namespace, rows: list) -> dict:
    """Timing and, when asked, the per-seed statistics of one example."""
    spec = EXAMPLES[name]
    params = {**spec["params"], **(spec["smoke"] if options.smoke else {})}
    entry = {"params": params, "steps": spec["steps"], "class": spec["cls"]}
    entry["timing"] = measure(name, params, options.rounds, options.core)
    if options.seeds > 1:
        pairs = collect(name, params, options.seeds, options.jobs, options.agree_cores)
        entry["stats"] = [{"original": o, "port": p} for o, p in pairs]
        rows += agree(name, pairs)
    shown = {k: v for k, v in entry["timing"].items() if k != "times"}
    print(name, json.dumps(shown), flush=True)
    return entry


def main() -> None:
    """Time each example, compare their statistics, write the JSON."""
    options = parse()
    core = options.core.split(",")[0].split("-")[0]
    out = {
        "environment": environment(ROOT, {"modelly": str(PYTHON)}, int(core)),
        "smoke": options.smoke, "seed_base": SEED_BASE, "examples": {},
    }  # fmt: skip
    rows = []
    for name in options.only:
        out["examples"][name] = example(name, options, rows)
    adjust(rows)
    out["agreement"] = rows
    options.output.write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
