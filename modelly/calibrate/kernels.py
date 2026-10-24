"""Perturbation kernels of ABC-SMC: move a particle, and the density of that move.

Continuous parameters move together under a multivariate normal whose
covariance is twice the weighted covariance of the previous population
(Beaumont et al., 2009). A choice keeps its value with probability ``stay``
and otherwise takes one of the other values, each equally likely.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from modelly.calibrate.priors import Prior

COVARIANCE_SCALE = 2.0
DEFAULT_STAY = 0.7
# Added to the covariance diagonal, relative to its scale, so it stays invertible.
RIDGE = 1e-9
MAX_REDRAWS = 1000


def joint_logprior(
    priors: Mapping[str, Prior], samples: Mapping[str, Sequence[Any]]
) -> np.ndarray:
    """The log prior density of every sample (independent priors)."""
    total = None
    for name, prior in priors.items():
        values = np.asarray(samples[name], dtype=object if prior.discrete else float)
        density = np.asarray(prior.logpdf(values), dtype=float)
        total = density if total is None else total + density
    return total


@dataclass
class Kernel:
    """A perturbation kernel fitted to a weighted population of particles."""

    priors: Mapping[str, Prior]
    population: Mapping[str, Sequence[Any]]
    weights: np.ndarray
    covariance: np.ndarray
    stay: float = DEFAULT_STAY

    @property
    def continuous(self) -> list[str]:
        """The names of the continuous parameters."""
        return [name for name, prior in self.priors.items() if not prior.discrete]

    @property
    def discrete(self) -> list[str]:
        """The names of the choice parameters."""
        return [name for name, prior in self.priors.items() if prior.discrete]

    @classmethod
    def fit(
        cls,
        priors: Mapping[str, Prior],
        samples: Mapping[str, Sequence[Any]],
        weights: np.ndarray,
    ) -> Kernel:
        """The kernel for moving the weighted population ``samples``."""
        names = [name for name, prior in priors.items() if not prior.discrete]
        if not names:
            return cls(priors, samples, weights, np.zeros((0, 0)))
        matrix = np.column_stack([np.asarray(samples[n], float) for n in names])
        covariance = np.atleast_2d(
            np.cov(matrix, rowvar=False, aweights=weights, bias=True)
        )
        scale = max(float(np.trace(covariance)) / len(names), 1.0)
        covariance = COVARIANCE_SCALE * covariance + RIDGE * scale * np.eye(len(names))
        return cls(priors, samples, weights, covariance)

    def perturb(
        self, samples: Mapping[str, Sequence[Any]], rng: np.random.Generator
    ) -> dict[str, list[Any]]:
        """Each of ``samples`` moved once (they may leave the prior's support)."""
        count = len(next(iter(samples.values())))
        moved: dict[str, list[Any]] = {}
        if self.continuous:
            matrix = np.column_stack(
                [np.asarray(samples[n], float) for n in self.continuous]
            )
            zero = np.zeros(len(self.continuous))
            matrix = matrix + rng.multivariate_normal(zero, self.covariance, size=count)
            moved |= {n: list(matrix[:, j]) for j, n in enumerate(self.continuous)}
        for name in self.discrete:
            moved[name] = self._move_choice(name, list(samples[name]), rng)
        return {name: moved[name] for name in self.priors}

    def _move_choice(
        self, name: str, values: list[Any], rng: np.random.Generator
    ) -> list[Any]:
        """Keep each value with probability ``stay``, else jump to another one."""
        options = list(self.priors[name].arguments["values"])
        keep = rng.random(len(values)) < self.stay
        jumps = rng.integers(0, max(len(options) - 1, 1), size=len(values))
        moved = []
        for value, stays, jump in zip(values, keep, jumps):
            others = [option for option in options if option != value]
            moved.append(value if stays or not others else others[int(jump)])
        return moved

    def logpdf(self, new: Mapping[str, Sequence[Any]]) -> np.ndarray:
        """``log K(new[i] | population[j])`` as an array ``[i, j]``."""
        old = self.population
        rows, cols = len(next(iter(new.values()))), len(self.weights)
        density = np.zeros((rows, cols))
        if self.continuous:
            from scipy.stats import multivariate_normal  # noqa: PLC0415 - lazy import

            a = np.column_stack([np.asarray(new[n], float) for n in self.continuous])
            b = np.column_stack([np.asarray(old[n], float) for n in self.continuous])
            normal = multivariate_normal(np.zeros(a.shape[1]), self.covariance)
            density += normal.logpdf(a[:, None, :] - b[None, :, :]).reshape(rows, cols)
        for name in self.discrete:
            density += self._choice_logpdf(name, new[name], old[name])
        return density

    def importance(self, new: Mapping[str, Sequence[Any]]) -> np.ndarray:
        """Unnormalised log weights: prior over the population's mixture density."""
        from scipy.special import logsumexp  # noqa: PLC0415 - lazy import

        mixture = logsumexp(np.log(self.weights)[None, :] + self.logpdf(new), axis=1)
        return joint_logprior(self.priors, new) - mixture

    def propose(self, rng: np.random.Generator, count: int) -> dict[str, list[Any]]:
        """``count`` particles: ancestors drawn by weight, moved until inside the prior."""
        ancestors = rng.choice(len(self.weights), size=count, p=self.weights)
        origin = {n: [v[i] for i in ancestors] for n, v in self.population.items()}
        proposal = self.perturb(origin, rng)
        for _ in range(MAX_REDRAWS):
            outside = np.flatnonzero(np.isneginf(joint_logprior(self.priors, proposal)))
            if not outside.size:
                return proposal
            retry = self.perturb(
                {n: [v[i] for i in outside] for n, v in origin.items()}, rng
            )
            for name, values in retry.items():
                for slot, value in zip(outside, values):
                    proposal[name][slot] = value
        raise RuntimeError("could not move particles inside the prior's support")

    def _choice_logpdf(
        self, name: str, new: Sequence[Any], old: Sequence[Any]
    ) -> np.ndarray:
        """``log P(new[i] | old[j])`` of the choice move."""
        others = len(self.priors[name].arguments["values"]) - 1
        if others == 0:
            return np.zeros((len(new), len(old)))
        same = np.array([[a == b for b in old] for a in new])
        jump = math.log((1 - self.stay) / others)
        return np.where(same, math.log(self.stay), jump)
