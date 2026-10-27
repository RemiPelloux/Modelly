"""Particle filter: keep an ensemble of runs close to the observations.

The bootstrap filter of Gordon, Salmond & Smith (1993), also called
sequential importance resampling. Each replicate of an
:class:`~modelly.stream.ensemble.Ensemble` is a particle. At each
observation the replicates run to its time (the model itself is the
proposal), each is weighted by
:meth:`ObservationOperator.log_likelihood <modelly.stream.operators.ObservationOperator.log_likelihood>`,
and when the effective sample size falls below ``threshold * n`` the
ensemble is resampled with systematic resampling (Douc & Cappé 2005;
Kitagawa 1996): a replicate drawn more than once is duplicated through a
checkpoint and the duplicates are reseeded so they diverge::

    pf = ParticleFilter(ensemble, observe, sd=5.0)
    pf.run(source)                       # assimilate every observation
    pf.estimate()                        # weighted mean of each quantity now
    pf.forecast(until=60)                # quantile bands ahead, a DataFrame

For a seed the filter is deterministic: the uniform of each systematic
resampling comes from a generator derived from the scenario's seed, and
duplicate ``slot`` of resampling ``g`` is reseeded from the derived key
``(RESAMPLE_DOMAIN, g, slot)``. Two runs give bit-identical weights and
replicates, with the compiled core or the pure-Python one.

References:
    Gordon, N. J., Salmond, D. J. & Smith, A. F. M. (1993). Novel approach to
    nonlinear/non-Gaussian Bayesian state estimation. IEE Proceedings F,
    140(2), 107-113.
    Douc, R. & Cappé, O. (2005). Comparison of resampling schemes for particle
    filtering. ISPA 2005, 64-69.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from modelly.stream.bands import DEFAULT_QUANTILES
from modelly.stream.ensemble import RESAMPLE_DOMAIN, Ensemble
from modelly.stream.sources import Observation, due

if TYPE_CHECKING:
    from modelly.stream.operators import ObservationOperator

DEFAULT_THRESHOLD = 0.5  # resample when ESS < half the ensemble
# The seed key of the generator drawing the systematic uniforms.
UNIFORMS_KEY = 0


def effective_sample_size(weights: Sequence[float]) -> float:
    """Kish's effective sample size of ``weights``: ``1 / sum(w**2)`` once they sum to one."""
    array = np.asarray(weights, dtype=float)
    share = array / array.sum()
    return float(1.0 / np.sum(share**2))


def systematic_resample(weights: Sequence[float], uniform: float) -> np.ndarray:
    """The replicates systematic resampling keeps, one index per slot, in order.

    Slot ``k`` takes the replicate whose cumulative weight first exceeds
    ``(uniform + k) / n``; one uniform in ``[0, 1)`` decides every slot, which
    gives the lowest resampling variance of the usual schemes (Douc & Cappé 2005).
    """
    if not 0.0 <= uniform < 1.0:
        raise ValueError(f"uniform must be in [0, 1), got {uniform}")
    array = np.asarray(weights, dtype=float)
    n = len(array)
    cumulative = np.cumsum(array / array.sum())
    cumulative[-1] = 1.0  # no slot falls past the end through rounding
    positions = (uniform + np.arange(n)) / n
    return np.searchsorted(cumulative, positions, side="right")


def _log_sum_exp(values: np.ndarray) -> float:
    """``log(sum(exp(values)))`` without overflow."""
    top = float(np.max(values))
    if not math.isfinite(top):
        return top
    return top + math.log(float(np.sum(np.exp(values - top))))


@dataclass(frozen=True)
class FilterStep:
    """What one assimilated observation did to the ensemble.

    ``log_evidence`` is the log of the observation's likelihood averaged over
    the weighted replicates before it, an estimate of ``log p(y_t | y_<t)``;
    the sum over steps estimates the log marginal likelihood of the data.
    """

    time: float
    ess: float
    resampled: bool
    log_evidence: float


class ParticleFilter:
    """Bootstrap particle filter over an ensemble (Gordon et al. 1993)."""

    def __init__(
        self,
        ensemble: Ensemble,
        operator: ObservationOperator,
        sd: float | Mapping[str, float],
        *,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        """Weight ``ensemble`` against observations read through ``operator``.

        ``sd`` is the observation error, one standard deviation for every
        quantity or one per quantity. ``threshold`` is the fraction of the
        ensemble size under which the effective sample size triggers a
        resampling: ``1.0`` resamples at every observation.
        """
        if not 0.0 < threshold <= 1.0:
            raise ValueError(f"threshold must be in (0, 1], got {threshold}")
        self.ensemble = ensemble
        self.operator = operator
        self.sd = sd
        self.threshold = threshold
        self._log_weights = np.zeros(len(ensemble))
        self._uniforms = np.random.default_rng(
            ensemble.seed(RESAMPLE_DOMAIN, UNIFORMS_KEY)
        )
        self._generation = 0
        self._steps: list[FilterStep] = []

    @property
    def weights(self) -> np.ndarray:
        """The normalised weight of each replicate."""
        return np.exp(self._log_weights - _log_sum_exp(self._log_weights))

    @property
    def ess(self) -> float:
        """The effective sample size of the current weights."""
        return effective_sample_size(self.weights)

    @property
    def resamplings(self) -> int:
        """How many times the ensemble has been resampled."""
        return self._generation

    def assimilate(self, observation: Observation) -> FilterStep:
        """Run the ensemble to ``observation``, weight it, resample when the ESS is low."""
        self.ensemble.advance(observation.time)
        likelihood = np.array(
            [
                self.operator.log_likelihood(model, observation, self.sd)
                for model in self.ensemble
            ]
        )
        likelihood[
            np.isnan(likelihood)
        ] = -np.inf  # an unreadable replicate scores zero
        prior = self._log_weights - _log_sum_exp(self._log_weights)
        posterior = prior + likelihood
        evidence = _log_sum_exp(posterior)
        if not math.isfinite(evidence):
            raise ValueError(
                f"every replicate has zero likelihood at time {observation.time}"
            )
        self._log_weights = posterior - evidence
        ess = self.ess
        resampled = ess < self.threshold * len(self.ensemble)
        if resampled:
            self._resample()
        step = FilterStep(observation.time, ess, resampled, evidence)
        self._steps.append(step)
        return step

    def _resample(self) -> None:
        """Systematic resampling, duplicates reseeded, weights back to equal."""
        indices = systematic_resample(self.weights, float(self._uniforms.random()))
        generation = self._generation
        self.ensemble.resample(
            indices, lambda slot: self.ensemble.seed(RESAMPLE_DOMAIN, generation, slot)
        )
        self._generation += 1
        self._log_weights = np.zeros(len(self.ensemble))

    def run(
        self, source: object | Iterable[Observation], until: float | None = None
    ) -> list[FilterStep]:
        """Assimilate every observation ``source`` has, up to ``until``.

        ``source`` is a stream source (anything with ``poll(until)``) or an
        iterable of observations in time order (see ``sources.due``).
        """
        return [self.assimilate(o) for o in due(source, until)]

    def estimate(self, operator: ObservationOperator | None = None) -> dict[str, float]:
        """The weighted mean of each quantity of ``operator`` (the filter's own by default)."""
        operator = operator or self.operator
        means = self.weights @ self.ensemble.values(operator)
        return dict(zip(operator.names, (float(m) for m in means)))

    def band(
        self,
        operator: ObservationOperator | None = None,
        quantiles: Sequence[float] = DEFAULT_QUANTILES,
    ) -> pd.DataFrame:
        """The weighted band of ``operator`` now (see :meth:`Ensemble.band`)."""
        return self.ensemble.band(operator or self.operator, quantiles, self.weights)

    def forecast(
        self,
        until: float,
        operator: ObservationOperator | None = None,
        *,
        every: float = 1.0,
        quantiles: Sequence[float] = DEFAULT_QUANTILES,
    ) -> pd.DataFrame:
        """The weighted band ahead to ``until`` (see :meth:`Ensemble.forecast`)."""
        return self.ensemble.forecast(
            operator or self.operator,
            until,
            every=every,
            quantiles=quantiles,
            weights=self.weights,
        )

    @property
    def history(self) -> pd.DataFrame:
        """One row per assimilated observation: time, ESS, resampled, log evidence."""
        columns = list(FilterStep.__dataclass_fields__)
        return pd.DataFrame([asdict(s) for s in self._steps], columns=columns)
