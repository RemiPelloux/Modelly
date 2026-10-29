"""Do the faster forms follow the same dynamics? Trajectories, patterns and rare events.

    python paper/scripts/trajectories.py run --seeds 100 --jobs 8    # data/trajectories.json
    python paper/scripts/trajectories.py analyse                     # tables and the figure

The agreement study (agreement.py) compares end-of-run summary statistics. Two
implementations could agree on those and still differ in how they get there: in the shape
of the epidemic curve, the spatial pattern it leaves, the speed at which a city segregates,
the period of a predator-prey cycle or how often a species dies out. This study compares
those, on three playbooks, over new shared seeds (disjoint from every other study's), each
Modelly variant and Mesa 3.5 against the Mesa 2.3 reference:

grid_epidemic   the whole infected curve; the peak's height and timing; the final size;
                the clusters of cells with anyone ever infected (count, largest, mean size)
schelling       the whole curve of the happy share and of the moves; the final
                segregation; the composition of every resident's neighbourhood (ten bins
                of the same-kind share); the number of steps before the moves fall under
                2% of the residents (the time to converge, capped at the run's length)
predator_prey   run for 2,000 steps rather than the playbook's 200, so that the cycle
                shows (at 200 steps the system is still in its first transient): the
                whole sheep, wolf and bare-grass curves; the probability that the wolves
                (or the sheep) die out within the run; the amplitude (over the second
                half) and period (first peak of the autocorrelation) of the sheep cycle

Prespecified margins (MARGINS below, fixed before the runs): curves are equivalent when the
95% upper bound of the largest standardised difference over all steps is under 0.5 s_p (as
in the primary study), and the scalars within a margin in their own units: 2 steps for a
timing, 0.02 for a share, 5 percentage points for a probability, 5% of Mesa's mean for a
count the primary study already covers, 10% for a derived quantity (clusters, amplitude,
period). Every scalar is tested by a paired TOST at that margin, the family of scalars
Holm-corrected; every curve by a seed bootstrap of the largest |d_t| and by a sign-flip
permutation test of the same statistic.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy import stats as sps

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent
HARNESS = ROOT / "benchmarks" / "playbooks"
DATA_DIR = PAPER / "data"
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(PAPER / "scripts"))

import compare  # noqa: E402
from agreement import ALPHA, compare_one, holm, tost_p  # noqa: E402
from agreement_tables import KINDS, LABELS, pvalue, signed  # noqa: E402
from environment import environment  # noqa: E402
from registry import PLAYBOOKS  # noqa: E402

REFERENCE = "mesa"
PLAYBOOK_VARIANTS = {
    "grid_epidemic": ["mesa", "mesa3", "modelly-cells", "modelly"],
    "schelling": ["mesa", "mesa3", "modelly-cells", "modelly"],
    "predator_prey": ["mesa", "mesa3", "modelly-cells", "modelly"],
}
PLAYBOOK_STEPS = {"predator_prey": 2000}  # the others run the playbook's own length
SEED_BASE = (
    20000  # disjoint from the primary studies (2000+) and the replications (10000+)
)
CURVE_MARGIN = 0.5  # in pooled standard deviations, per step
STRICT_CURVE_MARGIN = 0.25
BOOTSTRAPS = 2000
PERMUTATIONS = 2000
CONVERGED = 0.02  # moves under this share of the residents count as converged

# (kind, value): "abs" in the statistic's own units; "rel" as a share of Mesa's mean.
MARGINS: dict[tuple[str, str], tuple[str, float]] = {
    ("grid_epidemic", "peak_step"): ("abs", 2.0),
    ("grid_epidemic", "peak_I"): ("rel", 0.05),
    ("grid_epidemic", "final_R"): ("rel", 0.05),
    ("grid_epidemic", "clusters"): ("rel", 0.10),
    ("grid_epidemic", "largest_cluster"): ("rel", 0.10),
    ("grid_epidemic", "mean_cluster"): ("rel", 0.10),
    ("schelling", "segregation"): ("abs", 0.02),
    ("schelling", "final_happy"): ("abs", 0.02),
    ("schelling", "total_moves"): ("rel", 0.05),
    ("schelling", "steps_to_converge"): ("abs", 2.0),
    ("schelling", "composition"): ("abs", 0.02),
    ("predator_prey", "wolves_extinct"): ("abs", 0.05),
    ("predator_prey", "sheep_extinct"): ("abs", 0.05),
    ("predator_prey", "mean_sheep"): ("rel", 0.05),
    ("predator_prey", "mean_wolves"): ("rel", 0.05),
    ("predator_prey", "amplitude"): ("rel", 0.10),
    ("predator_prey", "period"): ("rel", 0.10),
}
QUANTITIES = {
    "peak_step": "peak timing (step)",
    "peak_I": "peak infected",
    "final_R": "final size",
    "clusters": "clusters of infected cells",
    "largest_cluster": "largest cluster",
    "mean_cluster": "mean cluster size",
    "segregation": "segregation (final)",
    "final_happy": "happy share (final)",
    "total_moves": "moves (total)",
    "steps_to_converge": "steps to converge",
    "composition": "composition bin",
    "wolves_extinct": "wolves die out (prob.)",
    "sheep_extinct": "sheep die out (prob.)",
    "mean_sheep": "mean sheep",
    "mean_wolves": "mean wolves",
    "amplitude": "sheep amplitude",
    "period": "sheep period (steps)",
}
CURVES = {
    "grid_epidemic": ["infected"],
    "schelling": ["happy", "moves"],
    "predator_prey": ["sheep", "wolves", "grass"],
}
CURVE_LABELS = {
    "infected": "infected",
    "happy": "happy share",
    "moves": "moves",
    "sheep": "sheep",
    "wolves": "wolves",
    "grass": "bare grass",
}


# --- running ----------------------------------------------------------------------------


def run_once(playbook: str, variant: str, seed: int, size: str) -> dict:
    """One run in a fresh interpreter of the variant's environment; its RESULT row."""
    command = [
        compare.interpreter(variant),
        str(PAPER / "scripts" / "trajectory_worker.py"),
        playbook,
        variant,
        str(seed),
        size,
        str(PLAYBOOK_STEPS.get(playbook, PLAYBOOKS[playbook]["steps"])),
    ]
    env = os.environ | {"POLARS_MAX_THREADS": "1"}
    completed = subprocess.run(
        command, capture_output=True, text=True, cwd=ROOT, check=False, env=env
    )
    for line in completed.stdout.splitlines():
        if line.startswith(compare.RESULT_PREFIX):
            row = json.loads(line[len(compare.RESULT_PREFIX) :])
            if "layer" in row:  # 0/1 per cell, packed as a string
                row["layer"] = "".join(str(x) for x in row["layer"])
            return row
    raise RuntimeError(
        f"{playbook}/{variant} seed {seed} failed:\n{completed.stderr[-2000:]}"
    )


def run(seeds: int, jobs: int, size: str, tag: str, base: int) -> None:
    """Every variant of the three playbooks on the same seeds; raw trajectories to a file."""
    tasks = [
        (name, variant, seed)
        for name, variants in PLAYBOOK_VARIANTS.items()
        for variant in variants
        for seed in range(base, base + seeds)
    ]

    def one(task: tuple[str, str, int]) -> tuple[str, str, int, dict]:
        name, variant, seed = task
        return name, variant, seed, run_once(name, variant, seed, size)

    raw: dict = {}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for name, variant, seed, row in pool.map(one, tasks):
            raw.setdefault(name, {}).setdefault(variant, {})[str(seed)] = row
    DATA_DIR.mkdir(exist_ok=True)
    payload = {
        "environment": environment(ROOT, compare.PYTHONS, None),
        "seeds": seeds,
        "seed_base": base,
        "size": size,
        "margins": {f"{p}/{q}": list(m) for (p, q), m in MARGINS.items()},
        "curve_margin": CURVE_MARGIN,
        "runs": raw,
    }
    out = DATA_DIR / f"trajectories_{tag}.json.gz"  # 1,200 trajectories: gzipped
    with gzip.open(out, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    print(f"{len(tasks)} runs written to {out}")


# --- derived quantities -------------------------------------------------------------------


def torus_clusters(layer: np.ndarray) -> np.ndarray:
    """Sizes of the 8-connected components of a 0/1 layer on a torus."""
    labels, count = ndimage.label(layer, structure=np.ones((3, 3), dtype=int))
    if count == 0:
        return np.zeros(0, dtype=int)
    parent = np.arange(count + 1)

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        if a and b:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)

    rows, cols = layer.shape
    for j in range(cols):  # top row touches bottom row (and its diagonals)
        for dj in (-1, 0, 1):
            union(labels[0, j], labels[rows - 1, (j + dj) % cols])
    for i in range(rows):  # left column touches right column (and its diagonals)
        for di in (-1, 0, 1):
            union(labels[i, 0], labels[(i + di) % rows, cols - 1])
    roots = np.array([find(k) for k in range(count + 1)])
    merged = roots[labels]
    sizes = np.bincount(merged.ravel())[1:]
    return sizes[sizes > 0]


def period_of(series: np.ndarray, min_lag: int = 20) -> float:
    """Lag of the first positive peak of the autocorrelation, or NaN when there is none."""
    x = series - series.mean()
    if np.all(x == 0):
        return math.nan
    acf = np.correlate(x, x, mode="full")[x.size - 1 :]
    acf = acf / acf[0]
    for lag in range(min_lag, acf.size - 1):
        if acf[lag] > 0 and acf[lag] >= acf[lag - 1] and acf[lag] > acf[lag + 1]:
            return float(lag)
    return math.nan


def scalars(playbook: str, row: dict) -> dict[str, float]:
    """The scalar quantities of one run."""
    stats, series = row["stats"], row["series"]
    if playbook == "grid_epidemic":
        side = row["side"]
        layer = np.frombuffer(row["layer"].encode(), dtype=np.uint8).reshape(side, side)
        sizes = torus_clusters((layer - ord("0")).astype(int))
        return {
            "peak_step": float(stats["peak_step"]),
            "peak_I": float(stats["peak_I"]),
            "final_R": float(stats["final_R"]),
            "clusters": float(sizes.size),
            "largest_cluster": float(sizes.max()) if sizes.size else 0.0,
            "mean_cluster": float(sizes.mean()) if sizes.size else 0.0,
        }
    if playbook == "schelling":
        moves = np.asarray(series["moves"], dtype=float)
        residents = row["residents"]
        shares = np.asarray(row["shares"], dtype=float) / max(residents, 1)
        out = {
            "segregation": float(stats["segregation"]),
            "final_happy": float(stats["final_happy"]),
            "total_moves": float(stats["total_moves"]),
            "steps_to_converge": float((moves > CONVERGED * residents).sum()),
        }
        out |= {f"composition_{k}": float(v) for k, v in enumerate(shares)}
        return out
    sheep = np.asarray(series["sheep"], dtype=float)
    wolves = np.asarray(series["wolves"], dtype=float)
    half = sheep.size // 2
    return {
        "wolves_extinct": float((wolves == 0).any()),
        "sheep_extinct": float((sheep == 0).any()),
        "mean_sheep": float(stats["mean_sheep"]),
        "mean_wolves": float(stats["mean_wolves"]),
        "amplitude": float(sheep[half:].max() - sheep[half:].min()),
        "period": period_of(sheep),
    }


# --- analysis -----------------------------------------------------------------------------


def margin_for(
    playbook: str, quantity: str, reference_mean: float
) -> tuple[str, float]:
    """The prespecified margin of a scalar, in its own units."""
    key = (
        quantity.split("_", maxsplit=1)[0]
        if quantity.startswith("composition")
        else quantity
    )
    kind, value = MARGINS[(playbook, key)]
    return kind, value if kind == "abs" else value * abs(reference_mean)


def scalar_rows(payload: dict) -> list[dict]:
    """One row per (playbook, variant, scalar): paired difference, d, TOST at the margin."""
    rows = []
    for playbook, variants in payload["runs"].items():
        seeds = sorted(variants[REFERENCE], key=int)
        reference = {s: scalars(playbook, variants[REFERENCE][s]) for s in seeds}
        for variant, runs in variants.items():
            if variant == REFERENCE:
                continue
            other = {s: scalars(playbook, runs[s]) for s in seeds}
            for quantity in reference[seeds[0]]:
                pairs = [
                    (reference[s][quantity], other[s][quantity])
                    for s in seeds
                    if not (
                        math.isnan(reference[s][quantity])
                        or math.isnan(other[s][quantity])
                    )
                ]
                a, b = [p[0] for p in pairs], [p[1] for p in pairs]
                if len(pairs) < 3:
                    print(
                        f"  {playbook} {variant} {quantity}: defined on {len(pairs)} seeds, skipped"
                    )
                    continue
                kind, margin = margin_for(playbook, quantity, statistics.fmean(a))
                diff = [y - x for x, y in zip(a, b, strict=True)]
                row = {
                    "playbook": playbook,
                    "variant": variant,
                    "quantity": quantity,
                    "kind": kind,
                    "margin": margin,
                    "defined": len(pairs),
                    "ref_mean": statistics.fmean(a),
                    "ref_sd": statistics.pstdev(a),
                    "tost_margin": tost_p(diff, margin),
                }
                if statistics.pvariance(a) or statistics.pvariance(b):
                    row |= compare_one(a, b)
                else:  # a constant in both arms (no extinction at all, say)
                    row |= {
                        "d": 0.0,
                        "d_lo": 0.0,
                        "d_hi": 0.0,
                        "paired": 1.0,
                        "mean_diff": 0.0,
                        "se_diff": 0.0,
                        "scale": 1.0,
                        "n": len(a),
                    }
                half = sps.t.ppf(1 - ALPHA / 2, len(diff) - 1) * row["se_diff"]
                row["diff_lo"], row["diff_hi"] = (
                    row["mean_diff"] - half,
                    row["mean_diff"] + half,
                )
                rows.append(row)
    for key in ("tost_margin", "paired"):
        for row, p in zip(rows, holm([r[key] for r in rows]), strict=True):
            row[f"{key}_holm"] = p
    return rows


def d_curve(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-step standardised paired difference and its 95% half-width; a, b: seeds x steps."""
    pooled = np.sqrt((a.var(axis=0, ddof=1) + b.var(axis=0, ddof=1)) / 2)
    scale = np.where(pooled > 0, pooled, 1.0)
    diff = b - a
    n = a.shape[0]
    d = diff.mean(axis=0) / scale
    half = (
        sps.t.ppf(1 - ALPHA / 2, n - 1)
        * diff.std(axis=0, ddof=1)
        / math.sqrt(n)
        / scale
    )
    return d, half, scale


def curve_rows(payload: dict, rng: np.random.Generator) -> list[dict]:
    """One row per (playbook, variant, series): the largest |d_t| with its bound and test."""
    rows = []
    for playbook, variants in payload["runs"].items():
        seeds = sorted(variants[REFERENCE], key=int)
        for series in CURVES[playbook]:
            a = np.array(
                [variants[REFERENCE][s]["series"][series] for s in seeds], float
            )
            ref_mean = a.mean(axis=0)
            for variant, runs in variants.items():
                if variant == REFERENCE:
                    continue
                b = np.array([runs[s]["series"][series] for s in seeds], float)
                d, half, scale = d_curve(a, b)
                diff = b - a
                n = a.shape[0]
                # seed bootstrap of sup_t |d_t|: resample seeds, keep each seed's pair
                sups = np.empty(BOOTSTRAPS)
                for k in range(BOOTSTRAPS):
                    pick = rng.integers(0, n, n)
                    sups[k] = np.abs(diff[pick].mean(axis=0) / scale).max()
                # sign-flip permutation test of the same statistic
                observed = np.abs(diff.mean(axis=0) / scale).max()
                flips = np.empty(PERMUTATIONS)
                for k in range(PERMUTATIONS):
                    signs = rng.choice([-1.0, 1.0], n)[:, None]
                    flips[k] = np.abs((diff * signs).mean(axis=0) / scale).max()
                big = (
                    ref_mean >= 0.1 * ref_mean.max()
                    if ref_mean.max() > 0
                    else ref_mean > 0
                )
                relative = (
                    float(np.abs(diff.mean(axis=0)[big] / ref_mean[big]).max())
                    if big.any()
                    else 0.0
                )
                rows.append(
                    {
                        "playbook": playbook,
                        "variant": variant,
                        "series": series,
                        "steps": int(a.shape[1]),
                        "sup_d": float(observed),
                        "sup_d_upper": float(np.quantile(sups, 0.95)),
                        "sup_d_upper99": float(np.quantile(sups, 0.99)),
                        "excluding_zero": int(((np.abs(d) - half) > 0).sum()),
                        "within_margin_steps": int(
                            ((np.abs(d) + half) < CURVE_MARGIN).sum()
                        ),
                        "permutation_p": float(
                            (np.sum(flips >= observed) + 1) / (PERMUTATIONS + 1)
                        ),
                        "relative_sup": relative,
                        "d": d.tolist(),
                        "half": half.tolist(),
                        "ref_mean": ref_mean.tolist(),
                        "mean": b.mean(axis=0).tolist(),
                        "ref_se": (a.std(axis=0, ddof=1) / math.sqrt(n)).tolist(),
                    }
                )
    return rows


def summary_table(scalar: list[dict], curves: list[dict], seeds: int) -> str:
    """One line per (workload, implementation): the curves and the scalars at a glance."""
    groups: dict[tuple[str, str], dict] = {}
    for row in curves:
        g = groups.setdefault(
            (row["playbook"], row["variant"]), {"curves": [], "scalars": []}
        )
        g["curves"].append(row)
    for row in scalar:
        groups[(row["playbook"], row["variant"])]["scalars"].append(row)
    lines = [
        "\\begin{tabular}{llrrrrrr}",
        "\\toprule",
        (
            "Workload & Implementation & Curves & $\\sup_t |d_t|$ & upper 95\\% & "
            "Scalars & max $|d|$ & Equivalent \\\\"
        ),
        "\\midrule",
    ]
    for (playbook, variant), g in groups.items():
        sup = max(r["sup_d"] for r in g["curves"])
        upper = max(r["sup_d_upper"] for r in g["curves"])
        sc = g["scalars"]
        passed = sum(r["tost_margin"] < ALPHA for r in sc)
        passed_holm = sum(r["tost_margin_holm"] < ALPHA for r in sc)
        lines.append(
            f"{LABELS[playbook]} & {KINDS[variant]} & {len(g['curves'])} & {sup:.2f} & "
            f"{upper:.2f} & {len(sc)} & {max(abs(r['d']) for r in sc):.2f} & "
            f"{passed}/{len(sc)} ({passed_holm}) \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines) + f"\n% {seeds} seeds per variant\n"


def margin_text(row: dict) -> str:
    """The margin as the paper states it."""
    kind, (_, value) = (
        row["kind"],
        MARGINS[
            (
                row["playbook"],
                "composition"
                if row["quantity"].startswith("composition")
                else row["quantity"],
            )
        ],
    )
    if kind == "rel":
        return f"$\\pm${value * 100:.0f}\\%"
    if row["quantity"] in ("wolves_extinct", "sheep_extinct"):
        return f"$\\pm${value * 100:.0f} pp"
    return f"$\\pm${value:g}"


def quantity_label(quantity: str) -> str:
    """The quantity's name in the table."""
    if quantity.startswith("composition_"):
        k = int(quantity.split("_")[1])
        return f"residents with same-kind share {k / 10:.1f}--{(k + 1) / 10:.1f}"
    return QUANTITIES[quantity]


def full_table(scalar: list[dict], seeds: int) -> str:
    """Every scalar comparison: Mesa's mean, the paired difference, d, margin, TOST p."""
    lines = [
        "\\begin{longtable}{llp{0.21\\linewidth}rp{0.19\\linewidth}rrrr}",
        (
            "\\caption{Every scalar comparison of the trajectory study over "
            f"{seeds} shared seeds at the small size (seeds {SEED_BASE} to {SEED_BASE + seeds - 1}): "
            "Mesa~2.3's mean, the mean paired difference (implementation minus Mesa~2.3) with its "
            "95\\% interval, the standardised difference $d$, the prespecified margin, and the "
            "paired TOST $p$-value at that margin, uncorrected and Holm-corrected over all "
            "the scalars of the study (the period is compared on the seeds where both arms "
            "define it). Generated by \\code{paper/scripts/trajectories.py}.}"
            "\\label{tab:trajectories-all}\\\\"
        ),
        "\\toprule",
        "Workload & Impl. & Quantity & Mesa & diff. [95\\%] & $d$ & margin & $p_{\\mathrm{TOST}}$ & Holm \\\\",
        "\\midrule",
        "\\endfirsthead",
        "\\toprule",
        "Workload & Impl. & Quantity & Mesa & diff. [95\\%] & $d$ & margin & $p_{\\mathrm{TOST}}$ & Holm \\\\",
        "\\midrule",
        "\\endhead",
        "\\bottomrule",
        "\\endfoot",
    ]
    for row in scalar:
        prob = row["quantity"].endswith("_extinct")
        fmt = (
            (lambda x: f"{x:.3f}")
            if (prob or row["ref_mean"] < 10)
            else (lambda x: f"{x:.1f}")
        )
        lines.append(
            f"{LABELS[row['playbook']]} & {KINDS[row['variant']]} & {quantity_label(row['quantity'])} & "
            f"{fmt(row['ref_mean'])} & ${row['mean_diff']:+.3g}$ [${row['diff_lo']:+.3g}$, ${row['diff_hi']:+.3g}$] & "
            f"{signed(row['d'])} & {margin_text(row)} & {pvalue(row['tost_margin'], 3)} & "
            f"{pvalue(row['tost_margin_holm'], 3)} \\\\"
        )
    lines.append("\\end{longtable}")
    return "\n".join(lines) + "\n"


def curve_table(curves: list[dict], seeds: int) -> str:
    """Every curve: the largest |d_t|, its bootstrap upper bound, the permutation test."""
    lines = [
        "\\begin{tabular}{lllrrrrrr}",
        "\\toprule",
        (
            "Workload & Impl. & Series & Steps & $\\sup_t |d_t|$ & upper 95\\% & "
            "steps $\\ni 0$ & rel. & $p_{\\mathrm{perm}}$ \\\\"
        ),
        "\\midrule",
    ]
    for row in curves:
        lines.append(
            f"{LABELS[row['playbook']]} & {KINDS[row['variant']]} & {CURVE_LABELS[row['series']]} & "
            f"{row['steps']} & {row['sup_d']:.2f} & {row['sup_d_upper']:.2f} & "
            f"{row['excluding_zero']} & {row['relative_sup'] * 100:.1f}\\% & "
            f"{pvalue(row['permutation_p'], 3)} \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines) + f"\n% {seeds} seeds per variant\n"


def figure(curves: list[dict], out: Path) -> None:
    """Mean curves of every implementation and the standardised difference per step."""
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415
    from figure_style import STYLE  # noqa: PLC0415

    plt.rcParams.update(STYLE)
    shown = [
        ("grid_epidemic", "infected"),
        ("schelling", "happy"),
        ("predator_prey", "sheep"),
    ]
    titles = {
        ("grid_epidemic", "infected"): "Grid epidemic: infected",
        ("schelling", "happy"): "Schelling: happy share",
        ("predator_prey", "sheep"): "Predator-prey: sheep",
    }
    colours = {"mesa3": "#999999", "modelly-cells": "#E69F00", "modelly": "#0072B2"}
    fig, axes = plt.subplots(2, 3, figsize=(9.6, 5.2), sharex="col")
    for col, key in enumerate(shown):
        rows = [r for r in curves if (r["playbook"], r["series"]) == key]
        top, bottom = axes[0, col], axes[1, col]
        ref = np.asarray(rows[0]["ref_mean"])
        se = np.asarray(rows[0]["ref_se"])
        steps = np.arange(1, ref.size + 1)
        top.fill_between(
            steps, ref - 2 * se, ref + 2 * se, color="black", alpha=0.15, lw=0
        )
        top.plot(steps, ref, color="black", lw=1.2, label="Mesa 2.3")
        for r in rows:
            top.plot(
                steps,
                r["mean"],
                color=colours[r["variant"]],
                lw=1.0,
                ls="--" if r["variant"] == "mesa3" else "-",
                label=KINDS[r["variant"]],
            )
            d, half = np.asarray(r["d"]), np.asarray(r["half"])
            bottom.fill_between(
                steps, d - half, d + half, color=colours[r["variant"]], alpha=0.2, lw=0
            )
            bottom.plot(steps, d, color=colours[r["variant"]], lw=1.0)
        bottom.axhline(0, color="black", lw=0.6)
        for m in (-CURVE_MARGIN, CURVE_MARGIN):
            bottom.axhline(m, color="black", lw=0.6, ls=":")
        top.set_title(titles[key], fontsize=9)
        bottom.set_xlabel("step")
        if col == 0:
            top.set_ylabel("mean over seeds")
            bottom.set_ylabel("$d_t$ (95% interval)")
        bottom.set_ylim(-1.0, 1.0)
    axes[0, 0].legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(out.with_suffix(".pdf"))
    fig.savefig(out.with_suffix(".png"), dpi=150)


def analyse(tag: str) -> None:
    """From the data file to the tables, the figure and a summary on stdout."""
    with gzip.open(
        DATA_DIR / f"trajectories_{tag}.json.gz", "rt", encoding="utf-8"
    ) as handle:
        payload = json.load(handle)
    rng = np.random.default_rng(1)
    scalar = scalar_rows(payload)
    curves = curve_rows(payload, rng)
    seeds = payload["seeds"]
    tables = PAPER / "tables"
    (tables / f"trajectories_{tag}.tex").write_text(
        summary_table(scalar, curves, seeds), encoding="utf-8"
    )
    (tables / f"trajectories_{tag}_curves.tex").write_text(
        curve_table(curves, seeds), encoding="utf-8"
    )
    (tables / f"trajectories_{tag}_all.tex").write_text(
        full_table(scalar, seeds), encoding="utf-8"
    )
    figure(curves, PAPER / "figures" / f"trajectories_{tag}")
    summary = {
        "scalars": scalar,
        "curves": [
            {
                k: v
                for k, v in r.items()
                if k not in ("d", "half", "ref_mean", "mean", "ref_se")
            }
            for r in curves
        ],
    }
    (DATA_DIR / f"trajectories_{tag}_summary.json").write_text(
        json.dumps(summary, indent=1), encoding="utf-8"
    )
    print(f"{len(curves)} curves and {len(scalar)} scalars over {seeds} seeds")
    for row in curves:
        print(
            f"  {row['playbook']:14s} {row['variant']:14s} {row['series']:9s} "
            f"sup|d| {row['sup_d']:.2f} upper {row['sup_d_upper']:.2f} "
            f"steps excl. 0: {row['excluding_zero']:3d}/{row['steps']} "
            f"rel {row['relative_sup'] * 100:.1f}% perm p {row['permutation_p']:.3f}"
        )
    modelly = [r for r in scalar if r["variant"].startswith("modelly")]
    mesa3 = [r for r in scalar if r["variant"] == "mesa3"]
    for label, rows in (("Modelly variants", modelly), ("Mesa 3.5", mesa3)):
        print(
            f"  {label}: {len(rows)} scalars, equivalent at the margin "
            f"{sum(r['tost_margin'] < ALPHA for r in rows)} uncorrected, "
            f"{sum(r['tost_margin_holm'] < ALPHA for r in rows)} after Holm; "
            f"paired t below {ALPHA}: {sum(r['paired'] < ALPHA for r in rows)} "
            f"({sum(r['paired_holm'] < ALPHA for r in rows)} after Holm); "
            f"max |d| {max(abs(r['d']) for r in rows):.2f}"
        )
    for row in scalar:
        if row["tost_margin"] >= ALPHA:
            print(
                f"    not shown equivalent: {row['playbook']} {row['variant']} {row['quantity']}: "
                f"Mesa {row['ref_mean']:.3g}, diff {row['mean_diff']:+.3g} "
                f"[{row['diff_lo']:+.3g}, {row['diff_hi']:+.3g}], margin {row['margin']:.3g}, "
                f"d {row['d']:+.2f}, p {row['tost_margin']:.3f}"
            )


def main() -> None:
    """Parse the command and run it."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["run", "analyse"])
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--size", choices=["small", "large"], default="small")
    parser.add_argument("--tag", default="small")
    parser.add_argument("--seed-base", type=int, default=SEED_BASE)
    options = parser.parse_args()
    if options.command == "run":
        run(options.seeds, options.jobs, options.size, options.tag, options.seed_base)
    else:
        analyse(options.tag)


if __name__ == "__main__":
    main()
