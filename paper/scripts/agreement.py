"""Do Modelly's playbook variants agree with Mesa in distribution? A larger-sample study.

    python paper/scripts/agreement.py run --size small --seeds 100   # data/agreement_small.json
    python paper/scripts/agreement.py analyse --size small           # tables/agreement_small.tex

`run` executes every variant of every playbook on the same seeds at the chosen size, through
the playbook harness (benchmarks/playbooks/compare.py, one fresh interpreter per run), and
stores every run's summary statistics. `analyse` compares each statistic of each Modelly
variant with the Mesa reference, seed by seed, by a paired t-test, a two-sample
Kolmogorov-Smirnov test and paired two one-sided tests (TOST) of equivalence within a margin of half a standard deviation, with
the Holm correction over all comparisons.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scipy import stats as sps

PAPER = Path(__file__).resolve().parents[1]
HARNESS = PAPER.parent / "benchmarks" / "playbooks"
DATA_DIR = PAPER / "data"
sys.path.insert(0, str(HARNESS))

import compare  # noqa: E402
from agreement_tables import forest, full_table, table  # noqa: E402
from environment import environment  # noqa: E402
from registry import PLAYBOOKS  # noqa: E402

REFERENCE = "mesa"
SEED_BASE = 2000  # disjoint from the harness's own agreement seeds (1000 and up)
# A replication draws new seeds (--seed-base 10000), disjoint from every primary study's.
MARGIN = 0.5  # equivalence margin, in pooled standard deviations
ALPHA = 0.05


GPU_SUFFIX = "-gpu"


def chosen(spec: dict, playbooks: list[str], variants: list[str]) -> list[str]:
    """The variants to run: the reference and those asked for (every Modelly one by default)."""
    if playbooks and spec["name"] not in playbooks:
        return []
    # The GPU variants draw from Philox streams and are reported with the GPU measurement.
    wanted = variants or [
        v
        for v in spec["variants"]
        if v.startswith("modelly") and not v.endswith(GPU_SUFFIX)
    ]
    return [v for v in spec["variants"] if v == REFERENCE or v in wanted]


def run(
    seeds: int, jobs: int, size: str, tag: str, only: tuple[list, list], base: int
) -> None:
    """The chosen variants of the chosen playbooks on the same seeds; raw statistics to a file."""
    tasks = [
        (name, variant, seed)
        for name, spec in PLAYBOOKS.items()
        for variant in chosen({"name": name, **spec}, *only)
        for seed in range(base, base + seeds)
    ]

    def one(task: tuple[str, str, int]) -> tuple[str, str, int, dict]:
        name, variant, seed = task
        return (
            name,
            variant,
            seed,
            compare.run_once(name, variant, seed, size, None)["stats"],
        )

    raw: dict = {}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for name, variant, seed, row in pool.map(one, tasks):
            raw.setdefault(name, {}).setdefault(variant, {})[str(seed)] = row
    DATA_DIR.mkdir(exist_ok=True)
    env = environment(PAPER.parent, compare.PYTHONS, None)
    payload = {"environment": env, "seeds": seeds, "seed_base": base, "size": size}
    payload["runs"] = raw
    out = DATA_DIR / f"agreement_{tag}.json"
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"{len(tasks)} runs written to {out}")


def tost_p(diff: list[float], margin: float) -> float:
    """Paired TOST p-value that the mean of the seed-by-seed differences is within the margin."""
    n, mean = len(diff), statistics.fmean(diff)
    se = statistics.stdev(diff) / math.sqrt(n)
    if se == 0:
        return 0.0 if abs(mean) < margin else 1.0
    lower = sps.t.sf((mean + margin) / se, n - 1)
    upper = sps.t.cdf((mean - margin) / se, n - 1)
    return float(max(lower, upper))


def compare_one(a: list[float], b: list[float]) -> dict:
    """Effect size with its paired 95% interval, and the three tests, for one statistic.

    ``a`` and ``b`` are aligned by seed: an implementation's run on seed s faces the other's
    run on seed s, and the two can share their initial state, so the tests are paired.
    """
    pooled = math.sqrt((statistics.variance(a) + statistics.variance(b)) / 2)
    scale = pooled or 1.0
    diff = [y - x for x, y in zip(a, b, strict=True)]
    n, spread = len(diff), statistics.stdev(diff)
    d = statistics.fmean(diff) / scale
    half = sps.t.ppf(1 - ALPHA / 2, n - 1) * spread / math.sqrt(n) / scale
    paired = sps.ttest_rel(b, a).pvalue if spread else 1.0
    linked = (
        statistics.correlation(a, b)
        if statistics.pvariance(a) and statistics.pvariance(b)
        else 1.0
    )
    return {
        "d": d,
        "d_lo": d - half,
        "d_hi": d + half,
        "paired": float(paired),
        "ks": float(sps.ks_2samp(a, b).pvalue),
        "levene": float(sps.levene(a, b, center="median").pvalue) if pooled else 1.0,
        "sd_ratio": statistics.stdev(b) / statistics.stdev(a)
        if statistics.pvariance(a)
        else 1.0,
        "tost": tost_p(diff, MARGIN * scale),
        "r": linked,
        "mean_diff": statistics.fmean(diff),
        "se_diff": spread / math.sqrt(n),
        "scale": scale,
        "n": n,
        "rel": statistics.fmean(diff) / abs(statistics.fmean(a))
        if statistics.fmean(a)
        else 0.0,
    }


def holm(p_values: list[float]) -> list[float]:
    """Holm-adjusted p-values, in the input order."""
    order = sorted(range(len(p_values)), key=p_values.__getitem__)
    adjusted, running = [0.0] * len(p_values), 0.0
    for rank, i in enumerate(order):
        running = max(running, (len(p_values) - rank) * p_values[i])
        adjusted[i] = min(1.0, running)
    return adjusted


def comparisons(payload: dict) -> list[dict]:
    """One row per (playbook, variant, statistic), with Holm-adjusted p-values."""
    rows = []
    for name, variants in payload["runs"].items():
        reference = variants[REFERENCE]
        for variant, runs in variants.items():
            # The GPU variants are not in the Holm family: they are reported with the GPU.
            if variant == REFERENCE or variant.endswith(GPU_SUFFIX):
                continue
            seeds = sorted(reference, key=int)
            for stat in reference[seeds[0]]:
                a = [float(reference[s][stat]) for s in seeds]
                b = [float(runs[s][stat]) for s in seeds]
                rows.append(
                    {"playbook": name, "variant": variant, "stat": stat}
                    | compare_one(a, b)
                )
    for key in ("paired", "ks", "tost", "levene"):
        for row, p in zip(rows, holm([r[key] for r in rows]), strict=True):
            row[f"{key}_holm"] = p
    return rows


def equivalent_at(rows: list[dict], margin: float) -> tuple[int, int]:
    """How many comparisons pass the paired TOST at ``margin`` s_p: uncorrected, and after Holm."""
    p_values = []
    for row in rows:
        bound, se, n = margin * row["scale"], row["se_diff"], row["n"]
        if se == 0:
            p_values.append(0.0 if abs(row["mean_diff"]) < bound else 1.0)
            continue
        lower = sps.t.sf((row["mean_diff"] + bound) / se, n - 1)
        upper = sps.t.cdf((row["mean_diff"] - bound) / se, n - 1)
        p_values.append(float(max(lower, upper)))
    raw = sum(p < ALPHA for p in p_values)
    return raw, sum(p < ALPHA for p in holm(p_values))


def analyse(tag: str) -> None:
    """Tests from the data file to the table, the figure and a summary on stdout."""
    payload = json.loads(
        (DATA_DIR / f"agreement_{tag}.json").read_text(encoding="utf-8")
    )
    rows = comparisons(payload)
    (PAPER / "tables" / f"agreement_{tag}.tex").write_text(
        table(rows, payload["seeds"]), encoding="utf-8"
    )
    forest(rows, PAPER / "figures" / f"agreement_{tag}")
    (PAPER / "tables" / f"agreement_{tag}_all.tex").write_text(
        full_table(rows, payload["seeds"], payload["size"], tag), encoding="utf-8"
    )
    summary = DATA_DIR / f"agreement_{tag}_summary.json"
    summary.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(
        f"{len(rows)} comparisons over {payload['seeds']} seeds; "
        f"paired t below {ALPHA} after Holm: {sum(r['paired_holm'] < ALPHA for r in rows)}; "
        f"KS: {sum(r['ks_holm'] < ALPHA for r in rows)}; "
        f"equivalent within {MARGIN} sd (per comparison): {sum(r['tost'] < ALPHA for r in rows)}; "
        f"max |d| {max(abs(r['d']) for r in rows):.2f}"
    )
    for margin in (0.25, 0.3, 0.4, 0.5):
        raw, corrected = equivalent_at(rows, margin)
        print(
            f"  margin {margin} s_p: {raw} equivalent uncorrected, {corrected} after Holm"
        )
    print(
        f"  paired t below {ALPHA} uncorrected: {sum(r['paired'] < ALPHA for r in rows)}; "
        f"KS: {sum(r['ks'] < ALPHA for r in rows)}; "
        f"intervals excluding 0: {sum(r['d_lo'] > 0 or r['d_hi'] < 0 for r in rows)}"
    )
    spread = [r["sd_ratio"] for r in rows]
    print(
        f"  Levene (spread) below {ALPHA}: {sum(r['levene'] < ALPHA for r in rows)}, "
        f"after Holm: {sum(r['levene_holm'] < ALPHA for r in rows)}; "
        f"sd ratio {min(spread):.2f} to {max(spread):.2f}"
    )


def main() -> None:
    """Parse the command and run it."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["run", "analyse"])
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--size", choices=["small", "large"], default="small")
    parser.add_argument(
        "--tag", default=None, help="data and table name (default: the size)"
    )
    parser.add_argument("--playbooks", nargs="*", default=[])
    parser.add_argument("--seed-base", type=int, default=SEED_BASE)
    parser.add_argument(
        "--variants", nargs="*", default=[], help="besides the reference"
    )
    options = parser.parse_args()
    tag = options.tag or options.size
    if options.command == "run":
        only = (options.playbooks, options.variants)
        run(options.seeds, options.jobs, options.size, tag, only, options.seed_base)
    else:
        analyse(tag)


if __name__ == "__main__":
    main()
