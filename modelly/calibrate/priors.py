"""Priors: what is believed about each parameter before the data are seen.

Example:
    >>> import numpy as np
    >>> prior = Prior.uniform(0.05, 0.5)
    >>> values = prior.sample(np.random.default_rng(1), 3)
    >>> bool(((values >= 0.05) & (values <= 0.5)).all())
    True
    >>> float(prior.logpdf(0.6))
    -inf

Continuous priors sample and evaluate through ``scipy.stats``; a choice draws
one of its values. Every draw comes from the generator passed in, so the same
seed gives the same samples.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

UNIFORM, LOG_UNIFORM, NORMAL = "uniform", "log_uniform", "normal"
LOG_NORMAL, TRUNCATED_NORMAL, CHOICE = "log_normal", "truncated_normal", "choice"
KINDS = (UNIFORM, LOG_UNIFORM, NORMAL, LOG_NORMAL, TRUNCATED_NORMAL, CHOICE)
# The interval an unbounded prior is searched over (optimisers, plots).
TAIL = 1e-3
MEDIAN = 0.5


def _plain(value: Any) -> Any:
    """A numpy scalar as the Python value it holds."""
    return value.item() if isinstance(value, np.generic) else value


@dataclass(frozen=True)
class Prior:
    """A prior distribution over one parameter; build it with a class method.

    Attributes:
        kind: one of ``uniform``, ``log_uniform``, ``normal``, ``log_normal``,
            ``truncated_normal`` and ``choice``.
        arguments: the distribution's parameters, by name.
    """

    kind: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Reject an unknown kind and impossible parameters."""
        if self.kind not in KINDS:
            raise ValueError(f"prior kind must be one of {KINDS}, got {self.kind!r}")
        self._check()

    def _check(self) -> None:
        """Raise ValueError for an empty interval, a scale <= 0 or no choices."""
        args = self.arguments
        if "low" in args and not args["low"] < args["high"]:
            raise ValueError(f"{self.kind} prior needs low < high, got {args}")
        if self.kind == LOG_UNIFORM and args["low"] <= 0:
            raise ValueError("a log-uniform prior needs low > 0")
        if args.get("sd", 1) <= 0 or args.get("sigma", 1) <= 0:
            raise ValueError(f"{self.kind} prior needs a positive scale, got {args}")
        if self.kind == CHOICE:
            self._check_choice(args["values"], args["probabilities"])

    @staticmethod
    def _check_choice(values: Sequence[Any], probabilities: Sequence[float]) -> None:
        """Values present and distinct; probabilities as many, >= 0, summing to 1."""
        if not values or len(set(values)) != len(values):
            raise ValueError("a choice prior needs distinct values")
        weights = np.asarray(probabilities, dtype=float)
        if len(weights) != len(values) or (weights < 0).any():
            raise ValueError("a choice prior needs one probability >= 0 per value")
        if not math.isclose(weights.sum(), 1.0):
            raise ValueError("the probabilities of a choice prior must sum to 1")

    @classmethod
    def uniform(cls, low: float, high: float) -> Prior:
        """Every value in ``[low, high]`` equally likely."""
        return cls(UNIFORM, {"low": float(low), "high": float(high)})

    @classmethod
    def log_uniform(cls, low: float, high: float) -> Prior:
        """Uniform on a log scale over ``[low, high]`` (``low > 0``)."""
        return cls(LOG_UNIFORM, {"low": float(low), "high": float(high)})

    @classmethod
    def normal(cls, mean: float, sd: float) -> Prior:
        """A normal distribution."""
        return cls(NORMAL, {"mean": float(mean), "sd": float(sd)})

    @classmethod
    def log_normal(cls, mu: float, sigma: float) -> Prior:
        """A value whose logarithm is normal with mean ``mu`` and sd ``sigma``."""
        return cls(LOG_NORMAL, {"mu": float(mu), "sigma": float(sigma)})

    @classmethod
    def truncated_normal(
        cls, mean: float, sd: float, low: float = -math.inf, high: float = math.inf
    ) -> Prior:
        """A normal distribution cut to ``[low, high]``."""
        arguments = {"mean": float(mean), "sd": float(sd)}
        return cls(TRUNCATED_NORMAL, arguments | {"low": low, "high": high})

    @classmethod
    def choice(
        cls, values: Sequence[Any], probabilities: Sequence[float] | None = None
    ) -> Prior:
        """One of ``values``, equally likely unless ``probabilities`` are given."""
        values = tuple(_plain(v) for v in values)
        count = max(len(values), 1)
        weights = [1 / count] * len(values) if probabilities is None else probabilities
        return cls(CHOICE, {"values": values, "probabilities": tuple(weights)})

    @property
    def discrete(self) -> bool:
        """Whether the prior is a choice among values."""
        return self.kind == CHOICE

    def distribution(self) -> Any:
        """The frozen ``scipy.stats`` distribution of a continuous prior."""
        from scipy import stats  # noqa: PLC0415 - scipy loads only when needed

        args = self.arguments
        if self.kind == UNIFORM:
            return stats.uniform(args["low"], args["high"] - args["low"])
        if self.kind == LOG_UNIFORM:
            return stats.loguniform(args["low"], args["high"])
        if self.kind == NORMAL:
            return stats.norm(args["mean"], args["sd"])
        if self.kind == LOG_NORMAL:
            return stats.lognorm(args["sigma"], scale=math.exp(args["mu"]))
        if self.kind == TRUNCATED_NORMAL:
            mean, sd = args["mean"], args["sd"]
            a, b = (args["low"] - mean) / sd, (args["high"] - mean) / sd
            return stats.truncnorm(a, b, loc=mean, scale=sd)
        raise TypeError("a choice prior has no scipy distribution")

    def sample(self, rng: np.random.Generator, size: int) -> np.ndarray:
        """``size`` independent draws from ``rng``."""
        if self.discrete:
            values = self.arguments["values"]
            picks = rng.choice(
                len(values), size=size, p=self.arguments["probabilities"]
            )
            return np.array([values[i] for i in picks], dtype=object)
        return np.asarray(self.distribution().rvs(size=size, random_state=rng))

    def logpdf(self, value: Any) -> float | np.ndarray:
        """The log density (log probability for a choice); ``-inf`` off the support."""
        if self.discrete:
            return self._log_probability(value)
        density: float | np.ndarray = self.distribution().logpdf(value)
        return density

    def _log_probability(self, value: Any) -> float | np.ndarray:
        """Log probability of one value or an array of values of a choice."""
        table = dict(zip(self.arguments["values"], self.arguments["probabilities"]))
        if isinstance(value, np.ndarray):
            return np.array([self._log_probability(v) for v in value], dtype=float)
        probability = table.get(_plain(value), 0.0)
        return math.log(probability) if probability > 0 else -math.inf

    def bounds(self) -> tuple[float, float]:
        """The support, or the central ``1 - 2 * TAIL`` interval of an unbounded prior."""
        if self.discrete:
            raise TypeError("a choice prior has no interval")
        low, high = self.distribution().support()
        if math.isinf(low) or math.isinf(high):
            low, high = self.distribution().ppf([TAIL, 1 - TAIL])
        return float(low), float(high)

    def median(self) -> Any:
        """The prior median (a choice: its most likely value)."""
        if self.discrete:
            probabilities = self.arguments["probabilities"]
            return self.arguments["values"][int(np.argmax(probabilities))]
        return float(self.distribution().ppf(MEDIAN))
