"""What the optimising methods share: a unit box over the priors and common random numbers.

:class:`~modelly.calibrate.moments.SimulatedMoments` and
:class:`~modelly.calibrate.bayesopt.BayesOpt` search the box spanned by the
priors (their support, or the central 99.8 % of an unbounded one; log-scaled
priors on a log scale). Every evaluation runs its point with the same
replicate seeds (common random numbers), so the objective is a deterministic,
smoother function of the parameters, and each evaluation is a batch of its own
in the store.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from modelly.calibrate.base import Calibration
from modelly.calibrate.posterior import Posterior
from modelly.calibrate.priors import LOG_NORMAL, LOG_UNIFORM, Prior
from modelly.calibrate.simulator import Batch, Execution

LOG_SCALED = (LOG_UNIFORM, LOG_NORMAL)
OBJECTIVE = "objective"


class UnitBox:
    """The map between the unit cube and the priors' search intervals."""

    def __init__(self, priors: Mapping[str, Prior]) -> None:
        """One interval per prior; choices are refused."""
        discrete = [name for name, prior in priors.items() if prior.discrete]
        if discrete:
            raise TypeError(f"this method fits continuous priors only, not {discrete}")
        self.names = list(priors)
        self.logs = [priors[n].kind in LOG_SCALED for n in self.names]
        bounds = [priors[n].bounds() for n in self.names]
        self.low = np.array(
            [math.log(b[0]) if log else b[0] for b, log in zip(bounds, self.logs)]
        )
        self.high = np.array(
            [math.log(b[1]) if log else b[1] for b, log in zip(bounds, self.logs)]
        )

    def params(self, unit: Sequence[float] | np.ndarray) -> dict[str, float]:
        """The parameters at ``unit`` (clipped to the cube)."""
        scaled = self.low + np.clip(np.asarray(unit, float), 0, 1) * (
            self.high - self.low
        )
        return {
            name: float(math.exp(v) if log else v)
            for name, v, log in zip(self.names, scaled, self.logs)
        }

    def unit(self, params: Mapping[str, float]) -> np.ndarray:
        """The position of ``params`` in the cube."""
        values = [
            math.log(params[n]) if log else params[n]
            for n, log in zip(self.names, self.logs)
        ]
        unit: np.ndarray = (np.asarray(values, float) - self.low) / (
            self.high - self.low
        )
        return unit


class PointEstimate(Calibration):
    """Base of the methods that return the best point found (a one-sample Posterior)."""

    key = 0  # first element of the method's batch keys

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Check the priors are continuous; nothing runs before ``run``."""
        super().__init__(*args, **kwargs)
        self.box = UnitBox(self.priors)
        self.evaluations: list[dict[str, Any]] = []

    def simulate(
        self,
        units: Sequence[Sequence[float] | np.ndarray] | np.ndarray,
        execution: Execution,
    ) -> list[dict[str, np.ndarray]]:
        """Run each unit-cube point as its own batch, with common random numbers."""
        start = len(self.evaluations)
        batches = [
            Batch(
                (self.key, start + i),
                self.points({n: [v] for n, v in self.box.params(u).items()}),
                common=True,
            )
            for i, u in enumerate(units)
        ]
        return [result[0] for result in self.simulator.run_many(batches, execution)]

    def record(
        self,
        unit: Sequence[float] | np.ndarray,
        value: float,
        summaries: Mapping[str, np.ndarray],
    ) -> float:
        """Keep one evaluation (parameters, objective, summaries); return ``value``."""
        entry = {**self.box.params(unit), OBJECTIVE: float(value)}
        record = {
            "row": entry,
            "unit": np.asarray(unit, float),
            "summaries": dict(summaries),
        }
        self.evaluations.append(record)
        return float(value)

    def trace(self) -> pd.DataFrame:
        """One row per evaluation: the parameters and the objective."""
        return pd.DataFrame([entry["row"] for entry in self.evaluations])

    def estimate(self) -> Posterior:
        """The best evaluation as a one-sample Posterior."""
        best = min(self.evaluations, key=lambda entry: entry["row"][OBJECTIVE])
        row = best["row"]
        samples = {name: [row[name]] for name in self.names}
        summaries = {
            name: values[None, :] for name, values in best["summaries"].items()
        }
        posterior = self.posterior(
            samples, np.ones(1), np.array([row[OBJECTIVE]]), summaries
        )
        posterior.info = {
            "evaluations": len(self.evaluations),
            OBJECTIVE: row[OBJECTIVE],
        }
        posterior.info |= {"runs": len(self.evaluations) * self.replicates}
        return posterior
