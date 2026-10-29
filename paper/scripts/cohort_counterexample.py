"""When cohorts keep the individual model's law, and two cases where they do not.

    python paper/scripts/cohort_counterexample.py      # data/cohort_counterexample.json

Section 3.2 states the proposition: a row of n individuals that each face, independently
and with the same probability s, one survival draw per phase, thinned by one
Binomial(n, s) draw, has the law of the individual model. This script checks the
proposition numerically on one phase and shows two ways of breaking its assumptions:

positive   homogeneous, synchronous: the individual model's survivors and the cohort's
           binomial draw have the same distribution (same mean and variance; a
           two-sample Kolmogorov-Smirnov test over the replicates finds no difference)
sequential density dependence: each individual's survival probability depends on the
           count alive when its turn comes (an asynchronous update), so the individuals
           do not share one probability within the phase; the cohort, which evaluates
           the rate once per phase, has a different mean
hidden heterogeneity: the individuals of a row differ in a variable the row does not
           carry (each has its own probability, with the right mean), so the survivors
           are Poisson-binomial, not binomial: same mean, smaller variance than the cohort

Every case uses 20,000 replicates of one phase on n = 200 individuals; the file holds the
means, variances and the test.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from environment import environment
from scipy import stats

PAPER = Path(__file__).resolve().parents[1]
REPLICATES, N, SEED = 20000, 200, 1
S = 0.8  # the survival probability at the start of the phase
SLOPE = 0.002  # sequential case: survival rises as the count alive falls (release)


def positive(rng: np.random.Generator) -> dict:
    """Homogeneous, synchronous: individual Bernoulli sum against one binomial draw."""
    individual = (rng.random((REPLICATES, N)) < S).sum(axis=1)
    cohort = rng.binomial(N, S, REPLICATES)
    return {
        "individual_mean": float(individual.mean()),
        "cohort_mean": float(cohort.mean()),
        "individual_var": float(individual.var()),
        "cohort_var": float(cohort.var()),
        "exact_mean": N * S,
        "exact_var": N * S * (1 - S),
        "ks_p": float(stats.ks_2samp(individual, cohort).pvalue),
    }


def sequential(rng: np.random.Generator) -> dict:
    """Density dependence evaluated when each individual's turn comes, not once per phase."""
    alive = np.full(REPLICATES, N)
    for _ in range(N):
        # the k-th individual survives with s(alive now): the rate rises as others die
        p = np.minimum(1.0, S + SLOPE * (N - alive))
        alive -= rng.random(REPLICATES) >= p
    cohort = rng.binomial(N, S, REPLICATES)  # the rate evaluated once, at the start
    diff = alive.mean() - cohort.mean()
    se = np.sqrt(alive.var() / REPLICATES + cohort.var() / REPLICATES)
    return {
        "individual_mean": float(alive.mean()),
        "cohort_mean": float(cohort.mean()),
        "individual_var": float(alive.var()),
        "cohort_var": float(cohort.var()),
        "difference": float(diff),
        "difference_se": float(se),
        "welch_p": float(stats.ttest_ind(alive, cohort, equal_var=False).pvalue),
    }


def heterogeneity(rng: np.random.Generator) -> dict:
    """Each individual its own probability, mean S: Poisson-binomial against binomial."""
    probabilities = rng.uniform(S - 0.2, S + 0.2, N)  # a hidden per-individual variable
    individual = (rng.random((REPLICATES, N)) < probabilities).sum(axis=1)
    cohort = rng.binomial(N, probabilities.mean(), REPLICATES)
    return {
        "individual_mean": float(individual.mean()),
        "cohort_mean": float(cohort.mean()),
        "individual_var": float(individual.var()),
        "cohort_var": float(cohort.var()),
        "exact_individual_var": float((probabilities * (1 - probabilities)).sum()),
        "exact_cohort_var": float(
            N * probabilities.mean() * (1 - probabilities.mean())
        ),
        "levene_p": float(stats.levene(individual, cohort, center="median").pvalue),
        "ks_p": float(stats.ks_2samp(individual, cohort).pvalue),
    }


def main() -> None:
    """Run the three cases and write the data file."""
    rng = np.random.default_rng(SEED)
    out = {
        "environment": environment(),
        "replicates": REPLICATES,
        "n": N,
        "survival": S,
        "positive": positive(rng),
        "sequential": sequential(rng),
        "heterogeneity": heterogeneity(rng),
    }
    (PAPER / "data" / "cohort_counterexample.json").write_text(
        json.dumps(out, indent=1) + "\n"
    )
    for case in ("positive", "sequential", "heterogeneity"):
        print(case, json.dumps(out[case], indent=1))


if __name__ == "__main__":
    main()
