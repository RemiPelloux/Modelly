"""Where does a speed-up come from? One ladder of implementations per workload.

    python paper/scripts/ablation.py --rounds 10 --core 2     # data/ablation.json
    python paper/scripts/ablation.py analyse                   # tables/ablation.tex

The playbook speed-ups compare two idioms whole: per-agent Mesa 3.5 code and Modelly's
column form. Between them several things change at once: the framework whose calls the
same code makes, whether those calls run in C or in Python, the data structure that holds
the population, the algorithm of a search, and whether a phase is written per agent or as
array operations. This script times a ladder of implementations that changes one of them
per rung, on four workloads, each rung a fresh interpreter pinned to one core, the rungs
rotating from round to round so that the per-round ratios are paired:

grid epidemic, Schelling
    Mesa 3.5                      per-agent code on Mesa's cell space
    migrated, Python core         the same code on Modelly (codemod), MODELLY_PURE_PYTHON=1:
                                  the framework's calls, in Python
    migrated, compiled core       the same, with the C modules: the compiled runtime
    cell lists, Python core       Modelly's cell lists (Mesa's data structure), with the
                                  obvious phases vectorised, framework calls in Python
    cell lists, compiled core     the same with the C modules
    columns, Python core          every phase as array operations over columns, no C
    columns, compiled core        the same with the C modules
    Mesa 3.5 + numpy              the array algorithm without agents or a framework layer
flocking
    Mesa 3.5                      per-agent, Mesa's all-pairs neighbour scan
    Mesa 3.5 + KD-tree            the same code with one cKDTree per step: the algorithm
    columns, Python core          Modelly's columns: KD-tree, steering as array operations
    columns, compiled core
Sugarscape
    Mesa 3.5                      per-agent, one search per forager
    cell lists, Python / compiled Modelly's cell lists with the same search algorithm:
                                  the data structure
    columns, Python / compiled    every forager's best cell in one array pass

Every rung keeps the playbook's parameters and random seed per round; what a rung computes
is checked by the agreement study, not here. The session runs at the machine's current
frequency policy (recorded), so its absolute times are not those of the main table; the
ratios between rungs are paired within the session.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent
sys.path.insert(0, str(ROOT / "benchmarks" / "playbooks"))

from environment import environment  # noqa: E402  (the harness's: commit, load, core, versions)

PLAYBOOKS = ROOT / "benchmarks" / "playbooks"
MIGRATED = ROOT / "benchmarks" / "migrated_mesa3"
PYTHON = ROOT / ".venv" / "bin" / "python"
PURE = {"MODELLY_PURE_PYTHON": "1"}
DATA = PAPER / "data" / "ablation.json"

# (label, base directory, module, extra environment, what changes from the rung above)
LADDERS: dict[str, list[tuple[str, Path, str, dict, str]]] = {
    "grid_epidemic": [
        ("Mesa 3.5", PLAYBOOKS, "mesa3_model", {}, "per-agent code on Mesa"),
        (
            "migrated, Python core",
            MIGRATED,
            "mesa3_model",
            PURE,
            "framework (same code, calls in Python)",
        ),
        ("migrated, compiled core", MIGRATED, "mesa3_model", {}, "compiled runtime"),
        (
            "cell lists, Python core",
            PLAYBOOKS,
            "modelly_cells",
            PURE,
            "obvious phases vectorised; C off",
        ),
        (
            "cell lists, compiled core",
            PLAYBOOKS,
            "modelly_cells",
            {},
            "compiled runtime",
        ),
        (
            "columns, Python core",
            PLAYBOOKS,
            "modelly_model",
            PURE,
            "representation: every phase as arrays; C off",
        ),
        ("columns, compiled core", PLAYBOOKS, "modelly_model", {}, "compiled runtime"),
        (
            "Mesa 3.5 + numpy",
            PLAYBOOKS,
            "mesa3np_model",
            {},
            "no agent objects, no framework layer",
        ),
    ],
    "schelling": [
        ("Mesa 3.5", PLAYBOOKS, "mesa3_model", {}, "per-agent code on Mesa"),
        (
            "migrated, Python core",
            MIGRATED,
            "mesa3_model",
            PURE,
            "framework (same code, calls in Python)",
        ),
        ("migrated, compiled core", MIGRATED, "mesa3_model", {}, "compiled runtime"),
        (
            "cell lists, Python core",
            PLAYBOOKS,
            "modelly_cells",
            PURE,
            "neighbour count vectorised; C off",
        ),
        (
            "cell lists, compiled core",
            PLAYBOOKS,
            "modelly_cells",
            {},
            "compiled runtime",
        ),
        (
            "columns, Python core",
            PLAYBOOKS,
            "modelly_model",
            PURE,
            "representation: every phase as arrays; C off",
        ),
        ("columns, compiled core", PLAYBOOKS, "modelly_model", {}, "compiled runtime"),
        (
            "Mesa 3.5 + numpy",
            PLAYBOOKS,
            "mesa3np_model",
            {},
            "no agent objects, no framework layer",
        ),
    ],
    "flocking": [
        ("Mesa 3.5", PLAYBOOKS, "mesa3_model", {}, "per-agent code, all-pairs scan"),
        (
            "Mesa 3.5 + KD-tree",
            PLAYBOOKS,
            "mesa3kd_model",
            {},
            "algorithm: one KD-tree per step",
        ),
        (
            "columns, Python core",
            PLAYBOOKS,
            "modelly_model",
            PURE,
            "representation: steering as arrays; C off",
        ),
        ("columns, compiled core", PLAYBOOKS, "modelly_model", {}, "compiled runtime"),
    ],
    "sugarscape": [
        (
            "Mesa 3.5",
            PLAYBOOKS,
            "mesa3_model",
            {},
            "per-agent code, one search per forager",
        ),
        (
            "cell lists, Python core",
            PLAYBOOKS,
            "modelly_cells",
            PURE,
            "data structure (same search); C off",
        ),
        (
            "cell lists, compiled core",
            PLAYBOOKS,
            "modelly_cells",
            {},
            "compiled runtime",
        ),
        (
            "columns, Python core",
            PLAYBOOKS,
            "modelly_model",
            PURE,
            "representation: search as one array pass; C off",
        ),
        ("columns, compiled core", PLAYBOOKS, "modelly_model", {}, "compiled runtime"),
    ],
}
LABELS = {
    "grid_epidemic": "Grid epidemic",
    "schelling": "Schelling",
    "flocking": "Flocking",
    "sugarscape": "Sugarscape",
}
ONE_RUN = """
import gc, importlib, importlib.util, json, sys, time, warnings
warnings.simplefilter("ignore")
base, name, module_name, seed, size = sys.argv[1:6]
spec = importlib.util.spec_from_file_location("registry", sys.argv[6])
registry = importlib.util.module_from_spec(spec); spec.loader.exec_module(registry)
play = registry.PLAYBOOKS[name]; params = {**play["params"], **play["sizes"][size]}
sys.path.insert(0, base); module = importlib.import_module(name + "." + module_name)
gc.collect(); t0 = time.process_time()
model = module.build(seed=int(seed), **params); t1 = time.process_time()
result = module.simulate(model, play["steps"]); t2 = time.process_time()
pure = None
try:
    from modelly._native import sets; pure = not sets.NATIVE
except Exception:
    pass
print(json.dumps({"build": t1 - t0, "run": t2 - t1, "pure": pure, "stats": result["stats"]}))
"""


def run_once(rung: tuple, name: str, seed: int, core: int | None) -> dict:
    """One rung once, in a fresh interpreter pinned to ``core``."""
    _, base, module, extra, _ = rung
    command = [str(PYTHON), "-c", ONE_RUN, str(base), name, module, str(seed), "large"]
    command.append(str(PLAYBOOKS / "registry.py"))
    if core is not None:
        command = ["taskset", "-c", str(core), *command]
    env = {k: v for k, v in os.environ.items() if k != "MODELLY_PURE_PYTHON"} | extra
    out = subprocess.run(command, capture_output=True, text=True, check=True, env=env)
    return json.loads(out.stdout.strip().splitlines()[-1])


def measure(name: str, rounds: int, core: int | None) -> dict:
    """Every rung of a ladder, ``rounds`` times, the order rotating from round to round."""
    ladder = LADDERS[name]
    times = {rung[0]: {"build": [], "run": [], "pure": None} for rung in ladder}
    for r in range(rounds):
        shift = r % len(ladder)
        for rung in ladder[shift:] + ladder[:shift]:
            row = run_once(rung, name, r, core)
            times[rung[0]]["build"].append(row["build"])
            times[rung[0]]["run"].append(row["run"])
            times[rung[0]]["pure"] = row["pure"]
            sys.stdout.write(
                f"  {name} {rung[0]:28s} round {r + 1}: build {row['build']:.3f} s, "
                f"run {row['run']:.3f} s cpu\n"
            )
            sys.stdout.flush()
    return times


RUNG_CHANGES = {
    "grid_epidemic": {
        "Mesa 3.5": "per-agent code on Mesa's cell space",
        "migrated": "same code, Modelly's calls (codemod)",
        "cell lists": "Mesa's data structure; infection phase as arrays",
        "columns": "every phase as arrays over columns",
        "Mesa 3.5 + numpy": "arrays without agent objects or framework",
    },
    "schelling": {
        "Mesa 3.5": "per-agent code on Mesa's cell space",
        "migrated": "same code, Modelly's calls (codemod)",
        "cell lists": "Mesa's data structure; neighbour count as arrays",
        "columns": "every phase as arrays over columns",
        "Mesa 3.5 + numpy": "arrays without agent objects or framework",
    },
    "flocking": {
        "Mesa 3.5": "per-agent code, all-pairs neighbour scan",
        "Mesa 3.5 + KD-tree": "same code, one KD-tree per step",
        "columns": "KD-tree; steering as arrays over columns",
    },
    "sugarscape": {
        "Mesa 3.5": "per-agent code, one search per forager",
        "cell lists": "Mesa's data structure, same search",
        "columns": "search as one array pass over columns",
    },
}


def rungs(name: str, times: dict) -> list[tuple[str, list | None, list | None]]:
    """The ladder regrouped: (rung, Python-core runs or None, compiled-core runs)."""
    out: dict[str, list] = {}
    for label, _base, _module, extra, _change in LADDERS[name]:
        rung = label.replace(", Python core", "").replace(", compiled core", "")
        slot = out.setdefault(rung, [None, None])
        slot[1 if not extra else 0] = times[label]["run"]
    return [(rung, slot[0], slot[1]) for rung, slot in out.items()]


def paired_ratio(a: list[float], b: list[float]) -> float:
    """Median of the per-round ratios a / b."""
    return statistics.median(x / y for x, y in zip(a, b, strict=True))


def analyse(payload: dict) -> str:
    """The LaTeX table: per rung, the step time with the Python and the compiled core, and the ratios."""
    lines = [
        "\\begin{tabularx}{\\linewidth}{l>{\\raggedright\\arraybackslash}Xrrrrr}",
        "\\toprule",
        " & & \\multicolumn{2}{c}{steps (s)} & & \\multicolumn{2}{c}{speed-up (compiled)} \\\\",
        "\\cmidrule(lr){3-4}\\cmidrule(lr){6-7}",
        "Workload & Rung & Python & compiled & C gain & Mesa~3.5 & rung above \\\\",
        "\\midrule",
    ]
    for name, times in payload["times"].items():
        ladder = rungs(name, times)
        base = ladder[0][2]
        previous = None
        for i, (rung, pure, compiled) in enumerate(ladder):
            change = RUNG_CHANGES[name][rung]
            c_gain = f"{paired_ratio(pure, compiled):.2f}" if pure is not None else "--"
            pure_s = f"{statistics.median(pure):.3f}" if pure is not None else "--"
            over_base = paired_ratio(base, compiled)
            over_prev = (
                f"{paired_ratio(previous, compiled):.2f}"
                if previous is not None
                else "--"
            )
            lines.append(
                f"{LABELS[name] if i == 0 else ''} & {rung}: {change} & {pure_s} & "
                f"{statistics.median(compiled):.3f} & {c_gain} & {over_base:.1f} & {over_prev} \\\\"
            )
            previous = compiled
        lines.append("\\addlinespace")
    lines.pop()
    lines += ["\\bottomrule", "\\end{tabularx}"]
    return (
        "\n".join(lines) + f"\n% {payload['rounds']} rounds, core {payload['core']}\n"
    )


def main() -> None:
    """Parse the options; measure or only re-analyse."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", nargs="?", default="run", choices=["run", "analyse"])
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--core", type=int, default=None)
    parser.add_argument("--playbooks", nargs="*", default=list(LADDERS))
    options = parser.parse_args()
    if options.command == "run":
        payload = {
            "environment": environment(ROOT, {"modelly": str(PYTHON)}, options.core),
            "rounds": options.rounds,
            "core": options.core,
            "ladders": {
                n: [
                    {"label": r[0], "module": r[2], "pure": bool(r[3]), "change": r[4]}
                    for r in LADDERS[n]
                ]
                for n in options.playbooks
            },
            "times": {
                n: measure(n, options.rounds, options.core) for n in options.playbooks
            },
        }
        DATA.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    (PAPER / "tables" / "ablation.tex").write_text(analyse(payload), encoding="utf-8")
    print(analyse(payload))


if __name__ == "__main__":
    main()
