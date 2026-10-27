"""Experimental designs: which points of a ScenarioSpace an experiment runs.

* :func:`full_factorial`: every combination, ``levels`` values per range;
* :func:`latin_hypercube`, :func:`sobol`, :func:`halton`: ``n`` points from
  ``scipy.stats.qmc``, scrambled from the experiment's seed;
* :func:`custom`: a list of points written by hand (or read from a file).

Example:
    >>> from modelly.experiments import ScenarioSpace, designs
    >>> space = ScenarioSpace(beta=(0.1, 0.3), policy=["a", "b"])
    >>> len(designs.full_factorial(levels=3).points(space))
    6
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import product
from typing import Any

import numpy as np
from scipy.stats import qmc

from modelly.experiments.space import ScenarioSpace

DEFAULT_LEVELS = 5


class Design:
    """Base class: ``points(space, rng)`` lists the parameter dicts to run."""

    kind = "design"

    def points(
        self, space: ScenarioSpace, rng: np.random.Generator | None = None
    ) -> list[dict[str, Any]]:
        """The design's points in ``space``; ``rng`` scrambles a random design."""
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """A JSON-ready description of the design."""
        return {"kind": self.kind, **vars(self)}


@dataclass
class FullFactorial(Design):
    """Every combination: ``levels`` evenly spaced values per range, every choice."""

    levels: int | Mapping[str, int] = DEFAULT_LEVELS
    kind = "full_factorial"

    def points(
        self, space: ScenarioSpace, rng: np.random.Generator | None = None
    ) -> list[dict[str, Any]]:
        """The Cartesian product of every dimension's levels, the last varying fastest."""
        axes = [
            dim.levels(self._levels_of(name)) for name, dim in space.dimensions.items()
        ]
        names = list(space.dimensions)
        return [space.complete(dict(zip(names, combo))) for combo in product(*axes)]

    def _levels_of(self, name: str) -> int:
        """The number of levels for ``name``."""
        if isinstance(self.levels, Mapping):
            return self.levels.get(name, DEFAULT_LEVELS)
        return self.levels


@dataclass
class _Sampled(Design):
    """``n`` points of a scipy.stats.qmc sampler, mapped from the unit cube."""

    n: int

    def __post_init__(self) -> None:
        """Reject an empty design."""
        if self.n < 1:
            raise ValueError(f"a design needs n >= 1 points, got {self.n}")

    def sampler(self, dimensions: int, rng: np.random.Generator) -> qmc.QMCEngine:
        """The scipy engine drawing the unit-cube sample."""
        raise NotImplementedError

    def points(
        self, space: ScenarioSpace, rng: np.random.Generator | None = None
    ) -> list[dict[str, Any]]:
        """``n`` points, the same for the same ``rng`` state."""
        rng = np.random.default_rng() if rng is None else rng
        count = len(space.dimensions)
        if count == 0:
            return [space.complete({})]
        sample = self.sampler(count, rng).random(self.n)
        return [space.point(row) for row in sample]


@dataclass
class LatinHypercube(_Sampled):
    """A Latin hypercube: each range cut in ``n`` strata, one point per stratum."""

    kind = "latin_hypercube"

    def sampler(self, dimensions: int, rng: np.random.Generator) -> qmc.QMCEngine:
        """The scipy LatinHypercube engine."""
        return qmc.LatinHypercube(dimensions, rng=rng)


@dataclass
class Sobol(_Sampled):
    """A scrambled Sobol sequence; balanced when ``n`` is a power of two."""

    kind = "sobol"

    def sampler(self, dimensions: int, rng: np.random.Generator) -> qmc.QMCEngine:
        """The scrambled scipy Sobol engine."""
        return qmc.Sobol(dimensions, scramble=True, rng=rng)


@dataclass
class Halton(_Sampled):
    """A scrambled Halton sequence (any ``n``)."""

    kind = "halton"

    def sampler(self, dimensions: int, rng: np.random.Generator) -> qmc.QMCEngine:
        """The scrambled scipy Halton engine."""
        return qmc.Halton(dimensions, scramble=True, rng=rng)


@dataclass
class Custom(Design):
    """Points given as a list of dicts; the space's fixed values fill the gaps."""

    rows: list[dict[str, Any]] = field(default_factory=list)
    kind = "custom"

    def points(
        self, space: ScenarioSpace, rng: np.random.Generator | None = None
    ) -> list[dict[str, Any]]:
        """The rows, completed with the fixed parameters and checked against the space."""
        if not self.rows:
            raise ValueError("a custom design needs at least one point")
        return [space.complete(row) for row in self.rows]


def full_factorial(levels: int | Mapping[str, int] = DEFAULT_LEVELS) -> FullFactorial:
    """Every combination of ``levels`` values per range (a mapping sets them per name)."""
    return FullFactorial(levels)


def latin_hypercube(n: int) -> LatinHypercube:
    """``n`` points of a Latin hypercube."""
    return LatinHypercube(n)


def sobol(n: int) -> Sobol:
    """``n`` points of a scrambled Sobol sequence (use a power of two)."""
    return Sobol(n)


def halton(n: int) -> Halton:
    """``n`` points of a scrambled Halton sequence."""
    return Halton(n)


def custom(rows: Sequence[Mapping[str, Any]]) -> Custom:
    """The points in ``rows``, one dict of parameter values each."""
    return Custom([dict(row) for row in rows])


DESIGNS: dict[str, Callable[..., Design]] = {
    "full_factorial": full_factorial,
    "latin_hypercube": latin_hypercube,
    "sobol": sobol,
    "halton": halton,
    "custom": custom,
}
