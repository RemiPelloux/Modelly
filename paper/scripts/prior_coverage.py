"""Coverage of ABC-SMC when the true parameters are drawn from the prior.

    python paper/scripts/prior_coverage.py run --replicates 300 --jobs 12   # data/
    python paper/scripts/prior_coverage.py analyse                          # stdout

recovery.py fixes six true points; nominal coverage is guaranteed only on average over
parameters drawn from the prior, so this script draws them: replicate r draws its true
parameters from the calibration's own prior (seed TRUTH_BASE + r), simulates the observed
series from them (data seed DATA_BASE + r), and calibrates with sampler seed r, with the
models and settings of recovery.py. Coverage is how often the true value lies in the 95%
highest-density interval, with a Clopper-Pearson interval.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER / "scripts"))
sys.path.insert(0, str(PAPER.parent))

from recovery import (  # noqa: E402
    DATA_BASE,
    GENERATIONS,
    MODELS,
    clopper_pearson,
    environment,
    shared,
)

from modelly.calibrate import ABCSMC, Prior, Target  # noqa: E402
from tests.calibrate.models import SIR, PreyPredator, log_counts  # noqa: E402

TRUTH_BASE = 7000
DATA = PAPER / "data" / "prior_coverage.json"


def priors(model: str) -> dict[str, Prior]:
    """The calibration's priors, which the true parameters are drawn from too."""
    if model == "SIR":
        return shared.sir_priors()
    return {
        "growth": Prior.uniform(0.2, 1.0),
        "predation": Prior.log_uniform(0.002, 0.05),
    }


def draw(model: str, replicate: int) -> dict[str, float]:
    """Replicate's true parameters, one draw from each prior."""
    rng = np.random.default_rng(TRUTH_BASE + replicate)
    return {n: float(p.sample(rng, 1)[0]) for n, p in priors(model).items()}


def calibration(model: str, truth: dict[str, float], replicate: int) -> ABCSMC:
    """recovery.py's calibration of ``model``, fitted to data simulated at ``truth``."""
    seed = DATA_BASE + replicate
    if model == "SIR":
        observed = shared.synthetic(SIR, truth, ["infected"], seed=seed)
        targets = [Target("infected", observed["infected"])]
        return ABCSMC(SIR, priors(model), targets, steps=shared.STEPS,
                      seed=replicate, particles=30)  # fmt: skip
    observed = shared.synthetic(PreyPredator, truth, ["prey", "predators"], seed=seed)
    targets = [Target(n, np.log1p(v), summary=log_counts) for n, v in observed.items()]
    return ABCSMC(PreyPredator, priors(model), targets, steps=shared.STEPS,
                  seed=replicate, particles=40)  # fmt: skip


def one(task: tuple[str, int]) -> dict:
    """One replicate: its truth and its posterior's HDI per parameter."""
    model, replicate = task
    truth = draw(model, replicate)
    summary = (
        calibration(model, truth, replicate).run(generations=GENERATIONS).summary()
    )
    rows = summary[["mean", "hdi_low", "hdi_high"]].to_dict("index")
    return {"model": model, "replicate": replicate, "truth": truth, "posterior": rows}


def run(replicates: int, jobs: int) -> None:
    """Every replicate of both models, written to data/prior_coverage.json."""
    tasks = [(m, r) for m in MODELS for r in range(1, replicates + 1)]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(one, tasks))
    payload = {
        "environment": environment(PAPER.parent, {"modelly": sys.executable}, None),
        "replicates": replicates,
        "runs": results,
    }
    DATA.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"{len(results)} calibrations written to {DATA}")


def analyse() -> None:
    """Coverage per model and parameter, with its Clopper-Pearson interval."""
    runs = json.loads(DATA.read_text(encoding="utf-8"))["runs"]
    for model in MODELS:
        mine = [r for r in runs if r["model"] == model]
        for name in priors(model):
            hits = sum(
                r["posterior"][name]["hdi_low"]
                <= r["truth"][name]
                <= r["posterior"][name]["hdi_high"]
                for r in mine
            )
            low, high = clopper_pearson(hits, len(mine))
            print(f"{model} {name}: {hits}/{len(mine)} = {hits / len(mine):.3f} "
                  f"[{low:.3f}, {high:.3f}]")  # fmt: skip


def main() -> None:
    """Parse the command and run it."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["run", "analyse"])
    parser.add_argument("--replicates", type=int, default=300)
    parser.add_argument("--jobs", type=int, default=8)
    options = parser.parse_args()
    if options.command == "run":
        run(options.replicates, options.jobs)
    analyse()


if __name__ == "__main__":
    main()
