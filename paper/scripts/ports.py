"""Same code on both frameworks: the public ports of benchmarks/ports against Mesa 2.3.

    python paper/scripts/ports.py --rounds 10 --core 2    # data/port_public.json

Each round runs the Mesa 2.3 original (benchmarks/playbooks/<playbook>/mesa_model.py, in
.venv-mesa2) and its port (benchmarks/ports/<playbook>/mesa_model.py, in .venv) in fresh
interpreters, alternating which goes first, pinned to one core, on the round's seed at the large
size; it records the CPU time of the steps and checks that the statistics are identical.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent
PLAYBOOKS = ("insect_cohorts", "boltzmann_wealth")
ARMS = {
    "mesa": (
        ROOT / ".venv-mesa2" / "bin" / "python",
        ROOT / "benchmarks" / "playbooks",
    ),
    "port": (ROOT / ".venv" / "bin" / "python", ROOT / "benchmarks" / "ports"),
}
ONE_RUN = """
import gc, importlib, importlib.util, json, sys, time, warnings
warnings.simplefilter("ignore")
base, name, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
spec = importlib.util.spec_from_file_location("registry", sys.argv[4])
registry = importlib.util.module_from_spec(spec); spec.loader.exec_module(registry)
play = registry.PLAYBOOKS[name]; params = {**play["params"], **play["sizes"]["large"]}
sys.path.insert(0, base); module = importlib.import_module(name + ".mesa_model")
model = module.build(seed=seed, **params); gc.collect(); start = time.process_time()
result = module.simulate(model, play["steps"])
print(json.dumps({"run": time.process_time() - start, "stats": result["stats"]}))
"""


def run(arm: str, name: str, seed: int, core: str) -> dict:
    """One run of one arm in a fresh interpreter, pinned to ``core``."""
    python, base = ARMS[arm]
    registry = ROOT / "benchmarks" / "playbooks" / "registry.py"
    command = [
        "taskset",
        "-c",
        core,
        str(python),
        "-c",
        ONE_RUN,
        str(base),
        name,
        str(seed),
    ]
    out = subprocess.run(
        [*command, str(registry)], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def measure(name: str, rounds: int, core: str) -> dict:
    """Paired rounds of one playbook: median times, ratio quartiles, identical statistics."""
    times, same = {arm: [] for arm in ARMS}, True
    for seed in range(rounds):
        order = ("mesa", "port") if seed % 2 == 0 else ("port", "mesa")
        results = {arm: run(arm, name, seed, core) for arm in order}
        for arm, result in results.items():
            times[arm].append(result["run"])
        same &= results["mesa"]["stats"] == results["port"]["stats"]
    ratios = [
        port / mesa for mesa, port in zip(times["mesa"], times["port"], strict=True)
    ]
    low, _, high = statistics.quantiles(ratios, n=4)
    return {
        "mesa": statistics.median(times["mesa"]),
        "port": statistics.median(times["port"]),
        "ratio": statistics.median(ratios),
        "lq": low, "uq": high, "min": min(ratios), "max": max(ratios),
        "identical": same, "rounds": rounds,
    }  # fmt: skip


def main() -> None:
    """Measure both ports and write data/port_public.json."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--core", default="2")
    options = parser.parse_args()
    out = {name: measure(name, options.rounds, options.core) for name in PLAYBOOKS}
    (PAPER / "data" / "port_public.json").write_text(json.dumps(out, indent=1))
    for name, row in out.items():
        print(name, json.dumps(row))


if __name__ == "__main__":
    main()
