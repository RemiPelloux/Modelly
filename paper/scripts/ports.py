"""Same code on both frameworks: the public ports against the Mesa originals.

    python paper/scripts/ports.py --rounds 10 --core 2    # data/port_public.json

Two sets of ports. ``benchmarks/ports`` holds two Mesa 2.3 playbooks ported line for line
(codemod plus the steps it reports); ``benchmarks/ports_mesa3`` holds five Mesa 3.5 playbooks
ported by the codemod alone. Each round runs an original and its port in fresh interpreters,
alternating which goes first, pinned to one core, on the round's seed at the large size, and
records the CPU time of the steps and whether the statistics are identical. For the Mesa 3.5
ports, whose random stream differs (Modelly derives ``model.random`` from the seed differently),
the statistics are also compared over shared seeds at the small size.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent
sys.path.insert(0, str(ROOT / "benchmarks" / "playbooks"))
sys.path.insert(0, str(PAPER / "scripts"))

from agreement import compare_one, holm  # noqa: E402
from environment import environment  # noqa: E402

PLAYBOOKS = ROOT / "benchmarks" / "playbooks"
SETS = {
    "mesa2": {
        "module": "mesa_model",
        "original": (ROOT / ".venv-mesa2" / "bin" / "python", PLAYBOOKS),
        "port": (ROOT / ".venv" / "bin" / "python", ROOT / "benchmarks" / "ports"),
        "playbooks": ("insect_cohorts", "boltzmann_wealth"),
    },
    "mesa3": {
        "module": "mesa3_model",
        "original": (ROOT / ".venv" / "bin" / "python", PLAYBOOKS),
        "port": (ROOT / ".venv" / "bin" / "python", ROOT / "benchmarks" / "ports_mesa3"),
        "playbooks": (
            "grid_epidemic", "network_contagion", "insect_cohorts", "schelling",
            "boltzmann_wealth",
        ),
    },
}  # fmt: skip
AGREEMENT_SEEDS, SEED_BASE = 100, 2000
ONE_RUN = """
import gc, importlib, importlib.util, json, sys, time, warnings
warnings.simplefilter("ignore")
base, name, module_name, seed, size = sys.argv[1:6]
spec = importlib.util.spec_from_file_location("registry", sys.argv[6])
registry = importlib.util.module_from_spec(spec); spec.loader.exec_module(registry)
play = registry.PLAYBOOKS[name]; params = {**play["params"], **play["sizes"][size]}
sys.path.insert(0, base); module = importlib.import_module(name + "." + module_name)
model = module.build(seed=int(seed), **params); gc.collect(); start = time.process_time()
result = module.simulate(model, play["steps"])
print(json.dumps({"run": time.process_time() - start, "stats": result["stats"]}))
"""


def run(
    arm: tuple, name: str, module: str, seed: int, size: str, core: str | None
) -> dict:
    """One run of one arm in a fresh interpreter, pinned to ``core`` when given."""
    python, base = arm
    command = [str(python), "-c", ONE_RUN, str(base), name, module, str(seed), size]
    command.append(str(PLAYBOOKS / "registry.py"))
    if core is not None:
        command = ["taskset", "-c", core, *command]
    out = subprocess.run(command, capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def measure(kind: dict, name: str, rounds: int, core: str) -> dict:
    """Paired rounds of one playbook: median times, ratio quartiles, identical statistics."""
    times, same = {"original": [], "port": []}, True
    for seed in range(rounds):
        order = ("original", "port") if seed % 2 == 0 else ("port", "original")
        out = {
            a: run(kind[a], name, kind["module"], seed, "large", core) for a in order
        }
        for arm, result in out.items():
            times[arm].append(result["run"])
        same &= out["original"]["stats"] == out["port"]["stats"]
    ratios = [p / o for o, p in zip(times["original"], times["port"], strict=True)]
    low, _, high = statistics.quantiles(ratios, n=4)
    return {
        "original": statistics.median(times["original"]),
        "port": statistics.median(times["port"]),
        "ratio": statistics.median(ratios), "lq": low, "uq": high,
        "min": min(ratios), "max": max(ratios), "identical": same, "rounds": rounds,
    }  # fmt: skip


def agree(kind: dict, name: str, jobs: int) -> list[dict]:
    """Each statistic of the port against the original over shared seeds, small size."""
    seeds = range(SEED_BASE, SEED_BASE + AGREEMENT_SEEDS)

    def both(seed: int) -> tuple[dict, dict]:
        return tuple(
            run(kind[arm], name, kind["module"], seed, "small", None)["stats"]
            for arm in ("original", "port")
        )

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        pairs = list(pool.map(both, seeds))
    return [
        {"stat": stat}
        | compare_one(
            [float(o[stat]) for o, _ in pairs], [float(p[stat]) for _, p in pairs]
        )
        for stat in pairs[0][0]
    ]


def main() -> None:
    """Time both sets of ports, compare the Mesa 3.5 ports, write data/port_public.json."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--core", default="2")
    parser.add_argument("--jobs", type=int, default=8)
    options = parser.parse_args()
    pythons = {
        "mesa2": str(SETS["mesa2"]["original"][0]),
        "modelly": str(SETS["mesa3"]["port"][0]),
    }
    out = {"environment": environment(ROOT, pythons, int(options.core))}
    for label, kind in SETS.items():
        out[label] = {
            n: measure(kind, n, options.rounds, options.core) for n in kind["playbooks"]
        }
    rows = []
    for name in SETS["mesa3"]["playbooks"]:
        rows += [
            {"playbook": name} | r for r in agree(SETS["mesa3"], name, options.jobs)
        ]
    for key in ("paired", "ks", "tost"):
        for row, p in zip(rows, holm([r[key] for r in rows]), strict=True):
            row[f"{key}_holm"] = p
    out["mesa3_agreement"] = rows
    (PAPER / "data" / "port_public.json").write_text(json.dumps(out, indent=1))
    for label in SETS:
        for name, row in out[label].items():
            print(label, name, json.dumps(row))


if __name__ == "__main__":
    main()
