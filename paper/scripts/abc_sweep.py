"""ABC-SMC coverage and diagnostics as the number of particles grows: a sweep.

    python paper/scripts/abc_sweep.py run --particles 30 60 100 200 --replicates 300
    python paper/scripts/abc_sweep.py analyse            # tables/abc_sweep.tex, stdout

prior_coverage.py measures coverage at one particle count. A coverage that is nominal at
one count on one model says nothing about another model, so a study needs a protocol
rather than a number: run the calibration at increasing particle counts and watch the
diagnostics converge. This script runs that protocol on the two models of recovery.py,
with the true parameters drawn from the prior (as prior_coverage.py does, same truth and
data seeds, so the datasets are the same at every particle count) and records, per
calibration, the coverage of the 95% highest-density interval, its width, the posterior's
effective sample size (Kish), the last generation's acceptance rate and tolerance, and the
model runs spent. ``analyse`` tabulates them by particle count.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER / "scripts"))
sys.path.insert(0, str(PAPER.parent))

from prior_coverage import DATA, calibration, draw, environment, priors  # noqa: E402
from recovery import GENERATIONS, MODELS, clopper_pearson  # noqa: E402

DEFAULT_PARTICLES = (30, 60, 100, 200)
PARAMETERS = {"SIR": ("beta", "gamma"), "Predator-prey": ("growth", "predation")}
LABELS = {
    "beta": r"$\beta$",
    "gamma": r"$\gamma$",
    "growth": "growth",
    "predation": "predation",
}


def data_file(particles: int) -> Path:
    """One file per particle count."""
    return DATA / f"abc_sweep_p{particles}.json"


def one(task: tuple[str, int, int]) -> dict:
    """One calibration: its truth, its intervals and its diagnostics."""
    model, replicate, particles = task
    truth = draw(model, replicate)
    smc = calibration(model, truth, replicate, particles)
    posterior = smc.run(generations=GENERATIONS)
    summary = posterior.summary()
    rows = summary[["mean", "hdi_low", "hdi_high"]].to_dict("index")
    last = smc.history[-1]
    return {
        "model": model,
        "replicate": replicate,
        "particles": particles,
        "truth": truth,
        "posterior": rows,
        "ess": posterior.effective_sample_size,
        "generations": len(smc.history),
        "acceptance": [g.acceptance for g in smc.history],
        "tolerance": [g.tolerance for g in smc.history],
        "runs": smc.runs,
        "final_acceptance": last.acceptance,
        "final_tolerance": last.tolerance,
    }


def run(particles: list[int], replicates: int, jobs: int) -> None:
    """Every replicate of both models at every particle count, one file per count."""
    for n in particles:
        tasks = [(m, r, n) for m in MODELS for r in range(1, replicates + 1)]
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(one, tasks))
        payload = {
            "environment": environment(PAPER.parent, {"modelly": sys.executable}, None),
            "replicates": replicates,
            "particles": n,
            "generations": GENERATIONS,
            "runs": results,
        }
        data_file(n).write_text(json.dumps(payload, indent=1), encoding="utf-8")
        print(f"{len(results)} calibrations at {n} particles written to {data_file(n)}")


def rows_for(particles: int) -> list[dict]:
    """Per model and parameter: coverage, interval width and the diagnostics."""
    payload = json.loads(data_file(particles).read_text(encoding="utf-8"))
    out = []
    for model in MODELS:
        mine = [r for r in payload["runs"] if r["model"] == model]
        for name in PARAMETERS[model]:
            hits = sum(
                r["posterior"][name]["hdi_low"]
                <= r["truth"][name]
                <= r["posterior"][name]["hdi_high"]
                for r in mine
            )
            low, high = clopper_pearson(hits, len(mine))
            prior = priors(model)[name]
            widths = [
                r["posterior"][name]["hdi_high"] - r["posterior"][name]["hdi_low"]
                for r in mine
            ]
            out.append(
                {
                    "particles": particles,
                    "model": model,
                    "parameter": name,
                    "n": len(mine),
                    "coverage": hits / len(mine),
                    "low": low,
                    "high": high,
                    "width": statistics.fmean(widths),
                    "ess": statistics.fmean(r["ess"] for r in mine),
                    "ess_share": statistics.fmean(
                        r["ess"] / r["particles"] for r in mine
                    ),
                    "acceptance": statistics.fmean(r["final_acceptance"] for r in mine),
                    "tolerance": statistics.fmean(r["final_tolerance"] for r in mine),
                    "runs": statistics.fmean(r["runs"] for r in mine),
                    "prior": str(prior),
                }
            )
    return out


def table(rows: list[dict]) -> str:
    """The sweep as a LaTeX table: one line per particle count, model and parameter."""
    lines = [
        "\\begin{tabular}{rllrrrrrr}",
        "\\toprule",
        (
            "Particles & Model & Parameter & Coverage & 95\\% interval & HDI width & "
            "ESS/N & Acceptance & Runs \\\\"
        ),
        "\\midrule",
    ]
    last = None
    for row in rows:
        key = (row["particles"], row["model"])
        if last is not None and key[0] != last[0]:
            lines.append("\\addlinespace")
        lines.append(
            f"{row['particles'] if key != last else ''} & "
            f"{row['model'] if key != last else ''} & {LABELS[row['parameter']]} & "
            f"{row['coverage'] * 100:.1f}\\% & [{row['low'] * 100:.1f}, {row['high'] * 100:.1f}] & "
            f"{row['width']:.3f} & {row['ess_share']:.2f} & {row['acceptance'] * 100:.0f}\\% & "
            f"{row['runs']:,.0f} \\\\"
        )
        last = key
    lines += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def analyse(particles: list[int]) -> None:
    """Tabulate every particle count that has a data file."""
    rows = [r for n in particles if data_file(n).exists() for r in rows_for(n)]
    (PAPER / "tables" / "abc_sweep.tex").write_text(table(rows), encoding="utf-8")
    (DATA / "abc_sweep_summary.json").write_text(
        json.dumps(rows, indent=1), encoding="utf-8"
    )
    for row in rows:
        print(
            f"{row['particles']:4d} {row['model']:14s} {row['parameter']:10s} "
            f"coverage {row['coverage']:.3f} [{row['low']:.3f}, {row['high']:.3f}] "
            f"width {row['width']:.3f} ESS/N {row['ess_share']:.2f} "
            f"acceptance {row['acceptance']:.2f} tolerance {row['tolerance']:.3g} runs {row['runs']:.0f}"
        )


def main() -> None:
    """Parse the command and run it."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["run", "analyse"])
    parser.add_argument(
        "--particles", type=int, nargs="*", default=list(DEFAULT_PARTICLES)
    )
    parser.add_argument("--replicates", type=int, default=300)
    parser.add_argument("--jobs", type=int, default=8)
    options = parser.parse_args()
    if options.command == "run":
        run(options.particles, options.replicates, options.jobs)
    analyse(options.particles)


if __name__ == "__main__":
    main()
