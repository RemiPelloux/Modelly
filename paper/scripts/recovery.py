"""Coverage of ABC-SMC parameter recovery: a fresh synthetic dataset for every replicate.

    python paper/scripts/recovery.py --replicates 50 --jobs 8   # data/recovery.json, tables/

Replicate r simulates the observed series from the true parameters with data seed
DATA_BASE + r, then calibrates it with sampler seed r, using the test suite's models and
settings (tests/calibrate). Coverage is how often the true value lies in the 95% highest-density
interval, with a Clopper-Pearson interval; errors are relative to the truth.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from scipy.stats import beta

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER.parent))

from modelly.calibrate import ABCSMC, Prior, Target  # noqa: E402
from tests.calibrate import shared  # noqa: E402
from tests.calibrate.models import SIR, PreyPredator, log_counts  # noqa: E402

sys.path.insert(0, str(PAPER.parent / "benchmarks" / "playbooks"))
from environment import environment  # noqa: E402

DATA_BASE = 5000
GENERATIONS = 6
LEVEL = 0.95
MODELS = ("SIR", "Predator-prey")
# Three true points per model across the priors; the first is the test suite's.
TRUTHS = {
    "SIR": (
        shared.SIR_TRUTH,
        {"beta": 0.25, "gamma": 0.05},
        {"beta": 0.6, "gamma": 0.2},
    ),
    "Predator-prey": (
        shared.PREY_TRUTH,
        {"growth": 0.35, "predation": 0.006},
        {"growth": 0.7, "predation": 0.02},
    ),
}


def calibration(model: str, point: int, replicate: int) -> ABCSMC:
    """The test suite's calibration of ``model``, fitted to replicate's own dataset."""
    seed = DATA_BASE + replicate
    if model == "SIR":
        observed = shared.synthetic(SIR, TRUTHS[model][point], ["infected"], seed=seed)
        targets = [Target("infected", observed["infected"])]
        return ABCSMC(SIR, shared.sir_priors(), targets, steps=shared.STEPS,
                      seed=replicate, particles=30)  # fmt: skip
    observed = shared.synthetic(
        PreyPredator, TRUTHS[model][point], ["prey", "predators"], seed=seed
    )
    targets = [Target(n, np.log1p(v), summary=log_counts) for n, v in observed.items()]
    priors = {  # as tests/calibrate/shared.py's prey_smc
        "growth": Prior.uniform(0.2, 1.0),
        "predation": Prior.log_uniform(0.002, 0.05),
    }
    return ABCSMC(PreyPredator, priors, targets, steps=shared.STEPS,
                  seed=replicate, particles=40)  # fmt: skip


def one(task: tuple[str, int, int]) -> dict:
    """One replicate's posterior summary, as plain numbers."""
    model, point, replicate = task
    summary = (
        calibration(model, point, replicate).run(generations=GENERATIONS).summary()
    )
    rows = summary[["mean", "median", "hdi_low", "hdi_high"]].to_dict("index")
    return {"model": model, "point": point, "replicate": replicate, "posterior": rows}


def truth(model: str, point: int = 0) -> dict[str, float]:
    """The true parameters of ``model`` at ``point``."""
    return TRUTHS[model][point]


def run(replicates: int, jobs: int) -> None:
    """Every replicate of both models, written to data/recovery.json."""
    tasks = [
        (m, k, r)
        for m in MODELS
        for k in range(len(TRUTHS[m]))
        for r in range(1, replicates + 1)
    ]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(one, tasks))
    out = PAPER / "data" / "recovery.json"
    payload = {
        "environment": environment(PAPER.parent, {"modelly": sys.executable}, None),
        "replicates": replicates,
        "runs": results,
    }
    out.write_text(json.dumps(payload, indent=1))
    print(f"{len(results)} calibrations written to {out}")


def clopper_pearson(hits: int, n: int) -> tuple[float, float]:
    """The exact 95% interval of a binomial proportion."""
    tail = (1 - LEVEL) / 2
    low = beta.ppf(tail, hits, n - hits + 1) if hits else 0.0
    high = beta.ppf(1 - tail, hits + 1, n - hits) if hits < n else 1.0
    return float(low), float(high)


def summarise(runs: list[dict], model: str, point: int, name: str) -> dict:
    """Errors of the posterior mean and median, and HDI coverage, for one parameter."""
    value = truth(model, point)[name]
    rows = [
        r["posterior"][name]
        for r in runs
        if r["model"] == model and r.get("point", 0) == point
    ]
    mean_err = [(row["mean"] - value) / value for row in rows]
    median_err = [(row["median"] - value) / value for row in rows]
    hits = sum(row["hdi_low"] <= value <= row["hdi_high"] for row in rows)
    return {
        "model": model, "name": name, "value": value, "n": len(rows),
        "mean_err": statistics.fmean(mean_err),
        "abs_mean_err": statistics.fmean(map(abs, mean_err)),
        "abs_median_err": statistics.fmean(map(abs, median_err)),
        "hits": hits, "coverage": clopper_pearson(hits, len(rows)),
    }  # fmt: skip


LABELS = {"beta": "$\\beta$", "gamma": "$\\gamma$", "growth": "growth",
          "predation": "predation"}  # fmt: skip


def table(rows: list[dict]) -> str:
    """The coverage table, booktabs."""
    lines = [
        "\\begin{tabular}{llrrrrl}",
        "\\toprule",
        (
            " & & \\multicolumn{2}{c}{Mean} & Median & \\multicolumn{2}{c}{In 95\\% HDI} \\\\ "
            "\\cmidrule(lr){3-4}\\cmidrule(lr){6-7} "
            "Model & Parameter & error & $|$error$|$ & $|$error$|$ & share & 95\\% CI \\\\"
        ),
        "\\midrule",
    ]
    for row in rows:
        low, high = row["coverage"]
        lines.append(
            f"{row['model']} & {LABELS[row['name']]} $= {row['value']:g}$ & "
            f"${100 * row['mean_err']:+.1f}\\%$ & {100 * row['abs_mean_err']:.1f}\\% & "
            f"{100 * row['abs_median_err']:.1f}\\% & {row['hits']}/{row['n']} & "
            f"[{low:.2f}, {high:.2f}] \\\\"
        )
    return "\n".join([*lines, "\\bottomrule", "\\end{tabular}"]) + "\n"


def analyse() -> None:
    """data/recovery.json to tables/recovery.tex and a summary on stdout."""
    payload = json.loads((PAPER / "data" / "recovery.json").read_text())
    rows = [
        summarise(payload["runs"], model, point, name)
        for model in MODELS
        for point in range(len(TRUTHS[model]))
        for name in truth(model, point)
    ]
    (PAPER / "tables" / "recovery.tex").write_text(table(rows), encoding="utf-8")
    for row in rows:
        print(row)


def main() -> None:
    """Parse the command and run it."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["run", "analyse"])
    parser.add_argument("--replicates", type=int, default=50)
    parser.add_argument("--jobs", type=int, default=8)
    options = parser.parse_args()
    run(options.replicates, options.jobs) if options.command == "run" else analyse()


if __name__ == "__main__":
    main()
