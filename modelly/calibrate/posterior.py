"""The result of a calibration: weighted parameter samples and how well they fit.

Example:
    >>> posterior = calibration.run(budget=2000)  # doctest: +SKIP
    >>> posterior.summary()  # mean, median, sd and HDI per parameter  # doctest: +SKIP
    >>> posterior.to_dataframe()  # one row per sample, with weight and distance  # doctest: +SKIP
    >>> posterior.predict(draws=20)  # posterior predictive runs  # doctest: +SKIP
    >>> posterior.plot()  # marginals, pairs, fit against the data  # doctest: +SKIP
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from modelly.calibrate.simulator import (
    DEFAULT_EXECUTOR,
    Batch,
    Execution,
    Stream,
    generator,
)

if TYPE_CHECKING:
    from modelly.calibrate.base import Calibration

DEFAULT_PROBABILITY = 0.95
DEFAULT_DRAWS = 20
MEDIAN = 0.5
# Slack on the cumulative weight, so an interval holding exactly ``probability`` counts.
ROUNDING = 1e-12
WEIGHT, DISTANCE, DRAW = "weight", "distance", "draw"


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    """The ``q`` quantile of ``values`` under ``weights`` (the inverse of the weighted CDF)."""
    order = np.argsort(values, kind="stable")
    cumulative = np.cumsum(weights[order]) / np.sum(weights)
    index = int(np.searchsorted(cumulative, q, side="left"))
    return float(values[order][min(index, len(values) - 1)])


def hdi(
    values: np.ndarray, weights: np.ndarray, probability: float
) -> tuple[float, float]:
    """The shortest interval holding ``probability`` of the weighted samples."""
    order = np.argsort(values, kind="stable")
    sorted_values = values[order]
    cumulative = np.concatenate([[0.0], np.cumsum(weights[order]) / np.sum(weights)])
    best = (float(sorted_values[0]), float(sorted_values[-1]))
    for start in range(len(sorted_values)):
        stop = int(
            np.searchsorted(cumulative, cumulative[start] + probability - ROUNDING)
        )
        if stop > len(sorted_values):
            break
        low, high = (
            float(sorted_values[start]),
            float(sorted_values[max(stop - 1, start)]),
        )
        if high - low < best[1] - best[0]:
            best = (low, high)
    return best


class Posterior:
    """Weighted samples of the fitted parameters.

    Attributes:
        samples: ``{parameter: values}``, one value per sample.
        weights: the normalised importance weights (all equal for rejection).
        distances: each sample's total distance to the targets.
        summaries: ``{target: array[sample, value]}``, what each sample simulated.
        calibration: the calibration that produced it (used by ``predict``).
    """

    def __init__(
        self,
        samples: Mapping[str, list[Any]],
        weights: np.ndarray,
        distances: np.ndarray,
        summaries: Mapping[str, np.ndarray],
        calibration: Calibration,
    ) -> None:
        """Keep the samples; the weights are normalised to sum to one."""
        weights = np.asarray(weights, dtype=float)
        self.samples = {name: list(values) for name, values in samples.items()}
        self.weights = weights / weights.sum()
        self.distances = np.asarray(distances, dtype=float)
        self.summaries = dict(summaries)
        self.calibration = calibration
        self.info: dict[str, Any] = {}

    def __len__(self) -> int:
        """The number of samples."""
        return len(self.weights)

    @property
    def effective_sample_size(self) -> float:
        """Kish's effective sample size of the weights, ``1 / sum(w**2)``."""
        return float(1.0 / np.sum(self.weights**2))

    @property
    def best(self) -> dict[str, Any]:
        """The parameters of the sample closest to the data."""
        index = int(np.argmin(self.distances))
        return {name: values[index] for name, values in self.samples.items()}

    def to_dataframe(self) -> pd.DataFrame:
        """One row per sample: the parameters, ``weight`` and ``distance``."""
        frame = pd.DataFrame(self.samples)
        frame[WEIGHT], frame[DISTANCE] = self.weights, self.distances
        return frame

    def numeric(self) -> dict[str, np.ndarray]:
        """The parameters whose values are numbers, as float arrays."""
        found = {}
        for name, values in self.samples.items():
            if all(
                isinstance(v, int | float) and not isinstance(v, bool) for v in values
            ):
                found[name] = np.asarray(values, dtype=float)
        return found

    def summary(self, probability: float = DEFAULT_PROBABILITY) -> pd.DataFrame:
        """Weighted mean, median, sd and highest-density interval per numeric parameter."""
        rows = {}
        for name, values in self.numeric().items():
            mean = float(np.sum(self.weights * values))
            sd = float(np.sqrt(np.sum(self.weights * (values - mean) ** 2)))
            low, high = hdi(values, self.weights, probability)
            median = weighted_quantile(values, self.weights, MEDIAN)
            rows[name] = {"mean": mean, "median": median, "sd": sd}
            rows[name] |= {"hdi_low": low, "hdi_high": high}
        return pd.DataFrame.from_dict(rows, orient="index")

    def resample(self, draws: int) -> list[int]:
        """``draws`` sample indices drawn with the weights, from the calibration's seed."""
        rng = generator(self.calibration.seed, Stream.PREDICTION, draws)
        return [int(i) for i in rng.choice(len(self), size=draws, p=self.weights)]

    def predict(
        self,
        draws: int = DEFAULT_DRAWS,
        executor: Any = DEFAULT_EXECUTOR,
        max_parallel: int | None = None,
        **options: Any,
    ) -> pd.DataFrame:
        """Run the model at ``draws`` posterior samples; one row per draw, replicate and step.

        The samples are drawn with the weights from the calibration's seed, and
        the runs go to ``executor`` (with ``options``) like the calibration's own.
        """
        calibration = self.calibration
        indices = self.resample(draws)
        values = {n: [self.samples[n][i] for i in indices] for n in calibration.names}
        batch = Batch((Stream.PREDICTION, draws), calibration.points(values))
        results = calibration.simulator.run(
            batch, Execution(executor, max_parallel, options)
        )
        rows = []
        for draw, (index, series) in enumerate(zip(indices, results)):
            for replicate in range(calibration.replicates):
                for step in range(calibration.steps + 1):
                    row = {
                        DRAW: draw,
                        "sample": index,
                        "replicate": replicate,
                        "step": step,
                    }
                    rows.append(
                        row | {n: s[replicate, step] for n, s in series.items()}
                    )
        return pd.DataFrame(rows)

    def plot(self, probability: float = DEFAULT_PROBABILITY) -> Any:
        """A Matplotlib figure: marginals and pairs of the parameters, fits against the data."""
        from modelly.calibrate.plots import posterior_figure  # noqa: PLC0415

        return posterior_figure(self, probability)

    def __repr__(self) -> str:
        """The method, the sample count and the effective sample size."""
        method = self.calibration.method
        return f"Posterior({method}, samples={len(self)}, ess={self.effective_sample_size:.1f})"
