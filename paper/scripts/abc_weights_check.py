"""Do the ABC-SMC weights of the code match the paper's equation (12)? Two checks.

    python paper/scripts/abc_weights_check.py      # data/abc_weights_check.json

Section 4.2 states that a proposal outside the prior's support is discarded and both the
ancestor and the move are drawn again, so that the proposal density is the whole mixture
truncated to the support, whose normalising constant is the same for every particle and
cancels in the weights. That is only right if the code truncates the mixture as a whole;
truncating each ancestor's kernel on its own and then mixing gives another density, with a
constant per ancestor that does not cancel. The two checks below tell the two apart.

A. The proposal density. A kernel is fitted to a population crowding the lower bound of
   a uniform prior and asked for 400,000 proposals. Their histogram is compared with the
   two candidate densities, the mixture truncated as a whole and the mixture of
   individually truncated kernels, bin by bin; and the code's log weights are compared
   with log prior minus log mixture, which must differ from them by one constant only.

B. The posterior. On a model whose ABC posterior at a tolerance is known in closed form
   (the mean of 20 normal draws with known spread, a uniform prior on the mean, the truth
   near the bound), ABC-SMC runs five generations and its weighted last population is
   compared with the exact ABC posterior at its final tolerance: weighted mean, quantiles
   and a weighted Kolmogorov-Smirnov distance. The same particles reweighted as the
   per-ancestor truncation would weight them are compared too, to show that the
   difference is detectable.

C. The settings of the coverage studies: the quantile, the kernel scale, the choice
   kernel's stay probability and the generations that prior_coverage.py and abc_sweep.py
   used, read from the objects they build, so that the paper's description can be checked
   against what ran.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from environment import environment
from scipy import stats

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER / "scripts"))
sys.path.insert(0, str(PAPER.parent))

from modelly import Model  # noqa: E402
from modelly.calibrate import ABCSMC, Prior, Target  # noqa: E402
from modelly.calibrate import kernels as kernels_module  # noqa: E402
from modelly.calibrate.kernels import Kernel, joint_logprior  # noqa: E402
from modelly.scenarios import Scenario  # noqa: E402

SEED = 1
PROPOSALS = 400_000
BINS = np.linspace(0.0, 0.4, 41)  # the region next to the bound, 40 bins of 0.01


# --- A: the proposal density ---------------------------------------------------------------


def check_density() -> dict:
    """The empirical proposal density against the two candidates, and the code's weights."""
    rng = np.random.default_rng(SEED)
    priors = {"mu": Prior.uniform(0.0, 1.0)}
    population = np.clip(rng.normal(0.05, 0.05, 2000), 1e-6, 1 - 1e-6)
    weights = rng.random(2000)
    weights /= weights.sum()
    kernel = Kernel.fit(priors, {"mu": list(population)}, weights)
    sd = float(np.sqrt(kernel.covariance[0, 0]))
    proposals = np.asarray(kernel.propose(rng, PROPOSALS)["mu"], float)
    counts, _ = np.histogram(proposals, bins=BINS)
    empirical = counts / PROPOSALS / np.diff(BINS)
    centres = (BINS[:-1] + BINS[1:]) / 2

    def mixture(x: np.ndarray) -> np.ndarray:
        return (
            weights[None, :] * stats.norm.pdf(x[:, None], population[None, :], sd)
        ).sum(axis=1)

    inside = stats.norm.cdf((1 - population) / sd) - stats.norm.cdf(
        (0 - population) / sd
    )
    whole = mixture(centres) / float((weights * inside).sum())  # one constant
    per_ancestor = (
        weights[None, :]
        / inside[None, :]
        * stats.norm.pdf(centres[:, None], population[None, :], sd)
    ).sum(axis=1)  # a constant per ancestor
    se = np.sqrt(counts) / PROPOSALS / np.diff(BINS)

    def deviation(candidate: np.ndarray) -> dict:
        z = (empirical - candidate) / se
        return {
            "max_relative": float(np.abs(empirical / candidate - 1).max()),
            "first_bin_relative": float(empirical[0] / candidate[0] - 1),
            "max_abs_z": float(np.abs(z).max()),
            "chi2_p": float(stats.chi2.sf((z**2).sum(), len(z))),
        }

    # the code's weights: log prior - log mixture, up to one constant
    log_w = kernel.importance({"mu": list(proposals[:5000])})
    expected = joint_logprior(priors, {"mu": list(proposals[:5000])}) - np.log(
        mixture(proposals[:5000])
    )
    return {
        "proposals": PROPOSALS,
        "kernel_sd": sd,
        "share_of_mass_outside_before_redraw": float(1 - (weights * inside).sum()),
        "whole_mixture_truncated": deviation(whole),
        "per_ancestor_truncated": deviation(per_ancestor),
        "weights_minus_formula_max_abs": float(np.abs(log_w - expected).max()),
        "bins": {
            "centre": centres.tolist(),
            "empirical": empirical.tolist(),
            "whole": whole.tolist(),
            "per_ancestor": per_ancestor.tolist(),
        },
    }


# --- B: the posterior ------------------------------------------------------------------------

NOISE, STEPS, TRUTH = 0.1, 20, 0.03


class MeanScenario(Scenario):
    """One parameter, the mean of the draws."""

    mu: float = 0.5


class MeanModel(Model):
    """Each step draws one normal number around ``mu``; the summary is their mean."""

    def __init__(self, scenario: MeanScenario = MeanScenario):  # noqa: D107
        super().__init__(scenario=scenario)
        self.y = float("nan")

    def step(self):  # noqa: D102
        self.y = self.scenario.mu + NOISE * float(self.rng.normal())


def series_mean(series: np.ndarray) -> float:
    """The mean of the draws (row 0 is the state before the first step)."""
    return float(np.nanmean(series[1:]))


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    """A weighted quantile."""
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    return float(values[order][np.searchsorted(cumulative, q * cumulative[-1])])


def check_posterior() -> dict:
    """ABC-SMC's weighted last population against the exact ABC posterior at its tolerance."""
    sigma = NOISE / np.sqrt(STEPS)
    truth = MeanModel(MeanScenario(mu=TRUTH, rng=99))
    observed = [truth.step() or truth.y for _ in range(STEPS)]
    y_obs = float(np.mean(observed))
    priors = {"mu": Prior.uniform(0.0, 1.0)}
    smc = ABCSMC(
        MeanModel,
        priors,
        [Target("y", [y_obs], summary=series_mean)],
        steps=STEPS,
        particles=2000,
        seed=SEED,
    )
    smc.run(generations=5)
    last = smc.history[-1]
    tolerance = last.tolerance
    particles = np.asarray(last.samples["mu"], float)
    weights = last.weights

    # the exact ABC posterior at this tolerance: prior x P(|ybar - y_obs| <= tolerance | mu)
    grid = np.linspace(0.0, 1.0, 100_001)
    accept = stats.norm.cdf((y_obs + tolerance - grid) / sigma) - stats.norm.cdf(
        (y_obs - tolerance - grid) / sigma
    )
    density = accept / np.trapezoid(accept, grid)
    cdf = np.cumsum(density) * (grid[1] - grid[0])
    cdf /= cdf[-1]
    exact_mean = float(np.trapezoid(grid * density, grid))
    exact_q = {q: float(grid[np.searchsorted(cdf, q)]) for q in (0.05, 0.5, 0.95)}

    def compare(w: np.ndarray) -> dict:
        w = w / w.sum()
        order = np.argsort(particles)
        empirical_cdf = np.cumsum(w[order])
        exact_at = np.interp(particles[order], grid, cdf)
        ks = float(np.abs(empirical_cdf - exact_at).max())
        return {
            "mean": float((w * particles).sum()),
            "quantiles": {
                str(q): weighted_quantile(particles, w, q) for q in (0.05, 0.5, 0.95)
            },
            "ks_distance": ks,
            "ess": float(1 / (w**2).sum()),
        }

    # the same particles weighted as the per-ancestor truncation would weight them
    previous = smc.history[-2]
    kernel = Kernel.fit(priors, previous.samples, previous.weights)
    sd = float(np.sqrt(kernel.covariance[0, 0]))
    ancestors = np.asarray(previous.samples["mu"], float)
    inside = stats.norm.cdf((1 - ancestors) / sd) - stats.norm.cdf((0 - ancestors) / sd)
    wrong_mixture = (
        previous.weights[None, :]
        / inside[None, :]
        * stats.norm.pdf(particles[:, None], ancestors[None, :], sd)
    ).sum(axis=1)
    wrong = 1.0 / wrong_mixture  # prior is flat on the support
    return {
        "y_obs": y_obs,
        "sigma_of_mean": float(sigma),
        "final_tolerance": float(tolerance),
        "generations": len(smc.history),
        "acceptance": [g.acceptance for g in smc.history],
        "exact": {
            "mean": exact_mean,
            "quantiles": {str(q): v for q, v in exact_q.items()},
        },
        "code_weights": compare(weights),
        "per_ancestor_weights": compare(wrong),
        "share_of_particles_within_2sd_of_bound": float((particles < 2 * sd).mean()),
        "kernel_sd": sd,
        "ks_monte_carlo_scale": float(1.36 / np.sqrt(1 / (weights**2).sum())),
    }


# --- C: the coverage studies' settings ------------------------------------------------------


def check_settings() -> dict:
    """What prior_coverage.py and abc_sweep.py build, read from the objects."""
    from prior_coverage import TEST_PARTICLES, calibration, draw  # noqa: PLC0415
    from recovery import GENERATIONS  # noqa: PLC0415

    out = {}
    for model, particles in (("SIR", None), ("SIR", 100), ("Predator-prey", None)):
        smc = calibration(model, draw(model, 1), 1, particles)
        out[f"{model} ({particles or TEST_PARTICLES[model]} particles)"] = {
            "particles": smc.particles,
            "quantile": smc.quantile,
            "min_tolerance": smc.min_tolerance,
            "min_acceptance": smc.min_acceptance,
            "replicates": smc.replicates,
            "generations_requested": GENERATIONS,
            "priors": {n: str(p) for n, p in smc.priors.items()},
        }
    out["kernel"] = {
        "covariance_scale": kernels_module.COVARIANCE_SCALE,
        "ridge": kernels_module.RIDGE,
        "choice_stay": kernels_module.DEFAULT_STAY,
        "redraw": "ancestor and move, until inside the support (Kernel.propose)",
    }
    return out


def main() -> None:
    """Run the checks and write the data file."""
    out = {
        "environment": environment(),
        "density": check_density(),
        "posterior": check_posterior(),
        "settings": check_settings(),
    }
    (PAPER / "data" / "abc_weights_check.json").write_text(
        json.dumps(out, indent=1) + "\n"
    )
    d, p = out["density"], out["posterior"]
    print(
        "A. proposal density against the candidates (max |z| over 40 bins, chi2 p, first bin):"
    )
    for name in ("whole_mixture_truncated", "per_ancestor_truncated"):
        c = d[name]
        print(
            f"   {name:24s} max|z| {c['max_abs_z']:.2f}  chi2 p {c['chi2_p']:.3f}  first bin {c['first_bin_relative']:+.3f}"
        )
    print(
        f"   code weights - (log prior - log mixture): max |diff| {d['weights_minus_formula_max_abs']:.2e}"
    )
    print(
        f"B. tolerance {p['final_tolerance']:.4f}; exact mean {p['exact']['mean']:.4f} q {p['exact']['quantiles']}"
    )
    for name in ("code_weights", "per_ancestor_weights"):
        c = p[name]
        print(
            f"   {name:20s} mean {c['mean']:.4f} q {c['quantiles']} KS {c['ks_distance']:.3f} ESS {c['ess']:.0f}"
        )
    print(f"   KS Monte Carlo scale {p['ks_monte_carlo_scale']:.3f}")
    print("C.", json.dumps(out["settings"], indent=1)[:600])


if __name__ == "__main__":
    main()
