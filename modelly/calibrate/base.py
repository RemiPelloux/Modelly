"""What every calibration method shares: model, priors, targets, seeds, runs, checkpoints.

A method subclasses :class:`Calibration` and implements ``run``. The base class
turns parameter samples into batches of runs on the experiment executors,
measures each point's distance to the targets, and saves the whole calibration,
state included, to a checkpoint that :meth:`Calibration.load` resumes.
"""

from __future__ import annotations

import os
import pickle
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

import modelly
from modelly.calibrate.posterior import Posterior
from modelly.calibrate.priors import Prior
from modelly.calibrate.simulator import Batch, Execution, Simulator
from modelly.calibrate.targets import Target, total_distance
from modelly.experiments.experiment import scenario_class
from modelly.experiments.scratch import scratch_folder
from modelly.experiments.space import Fixed, ScenarioSpace
from modelly.experiments.store import RESERVED
from modelly.experiments.tasks import reference, resolve

DEFAULT_STEPS = 100
MAGIC = b"MODELLY-CALIBRATION\n"
PICKLE_PROTOCOL = pickle.HIGHEST_PROTOCOL
TEMP_SUFFIX = ".tmp"


class CalibrationError(RuntimeError):
    """A calibration cannot go on (no particle accepted, a checkpoint is unusable...)."""


def _plain(value: Any) -> Any:
    """A numpy scalar as the Python value it holds."""
    return value.item() if isinstance(value, np.generic) else value


class Calibration:
    """Base class: fit the priors' parameters of ``model`` to ``targets``.

    Args:
        model: the Model class, or ``"package.module:Class"`` / ``"path/model.py:Class"``.
        priors: ``{parameter: Prior}`` for every parameter to fit.
        targets: the observed quantities (:class:`~modelly.calibrate.targets.Target`).
        steps: steps per run.
        replicates: runs per parameter point, averaged before the distance.
        seed: the root of every random stream: same seed, same result.
        store: the folder the runs are written to (a temporary one by default);
            a calibration rerun into the same folder reads the runs already there.
        fixed: parameters every run takes, not fitted.
    """

    method = "calibration"
    # Each method defines run(...) with its own options; it returns a Posterior.
    run: Callable[..., Posterior]

    def __init__(
        self,
        model: type | str,
        priors: Mapping[str, Prior],
        targets: Sequence[Target],
        steps: int = DEFAULT_STEPS,
        replicates: int = 1,
        seed: int = 0,
        store: str | Path | None = None,
        fixed: Mapping[str, Any] | None = None,
    ) -> None:
        """Check the definition; nothing runs before ``run``."""
        self.model = model if isinstance(model, str) else reference(model)
        self.priors, self.targets = dict(priors), list(targets)
        self.steps, self.replicates, self.seed = steps, replicates, seed
        self.fixed = {name: _plain(value) for name, value in (fixed or {}).items()}
        self.store = None if store is None else Path(store).resolve()
        self._validate()
        self._temporary: Path | None = None

    def _validate(self) -> None:
        """Reject an empty or inconsistent definition before anything runs."""
        if not self.priors or not self.targets:
            raise ValueError("a calibration needs at least one prior and one target")
        if self.steps < 0 or self.replicates < 1 or self.seed < 0:
            raise ValueError("steps >= 0, replicates >= 1 and seed >= 0 are required")
        names = [*self.priors, *self.fixed, *(t.name for t in self.targets)]
        clashes = {n for n in names if names.count(n) > 1} | (
            set(names) & set(RESERVED)
        )
        if clashes:
            raise ValueError(f"names used twice or reserved: {sorted(clashes)}")
        for target in self.targets:
            target.check_length(self.steps)
        scenario = scenario_class(resolve(self.model))
        if scenario is not None:
            values = {n: Fixed(p.median()) for n, p in self.priors.items()}
            ScenarioSpace({**values, **self.fixed}).typed(scenario)

    @property
    def names(self) -> list[str]:
        """The fitted parameters, in the priors' order."""
        return list(self.priors)

    @property
    def simulator(self) -> Simulator:
        """The runs' simulator, writing to the store (or a temporary folder)."""
        if self.store is None and self._temporary is None:
            self._temporary = scratch_folder(self, "modelly-calibrate-")
        root = self.store or self._temporary
        assert root is not None  # a store, or the scratch folder made above
        outputs = {target.name: target.spec for target in self.targets}
        return Simulator(
            self.model, outputs, self.steps, self.replicates, self.seed, root
        )

    def points(self, samples: Mapping[str, Sequence[Any]]) -> list[dict[str, Any]]:
        """One parameter dict per sample, the fixed parameters included."""
        count = len(next(iter(samples.values())))
        return [
            {**self.fixed, **{n: _plain(samples[n][i]) for n in self.names}}
            for i in range(count)
        ]

    def evaluate(
        self, batch: Batch, execution: Execution
    ) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        """Run ``batch``; the total distance and every target's summary, per point."""
        return self.measure(self.simulator.run(batch, execution))

    def measure(
        self, results: Sequence[Mapping[str, np.ndarray]]
    ) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        """The total distance and every target's summary of simulated ``results``."""
        summaries = {
            t.name: [t.simulated(r[t.name]) for r in results] for t in self.targets
        }
        distances = [
            total_distance(self.targets, {n: s[i] for n, s in summaries.items()})
            for i in range(len(results))
        ]
        return np.asarray(distances, float), {
            n: np.vstack(s) for n, s in summaries.items()
        }

    def posterior(
        self,
        samples: Mapping[str, Sequence[Any]],
        weights: np.ndarray,
        distances: np.ndarray,
        summaries: Mapping[str, np.ndarray],
    ) -> Posterior:
        """The Posterior of weighted samples, with what it needs to predict and plot."""
        frame = {name: list(samples[name]) for name in self.names}
        return Posterior(frame, weights, distances, dict(summaries), self)

    def save(self, path: str | Path) -> None:
        """Write the calibration and its progress to ``path`` (a pickle; trusted files only).

        Every model, distance and summary function must be importable (no lambdas).
        """
        try:
            payload = pickle.dumps(self, PICKLE_PROTOCOL)
        except (pickle.PicklingError, AttributeError, TypeError) as error:
            raise CalibrationError(
                f"cannot save the calibration: {error}. Use module-level functions "
                "for distances, summaries and outputs, not lambdas or closures."
            ) from error
        path = Path(path)
        temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}{TEMP_SUFFIX}")
        try:
            temp.write_bytes(MAGIC + modelly.__version__.encode() + b"\n" + payload)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    @classmethod
    def load(cls, path: str | Path) -> Calibration:
        """The calibration :meth:`save` wrote; ``run`` it again to go on where it stopped."""
        with Path(path).open("rb") as file:
            if file.readline() != MAGIC:
                raise CalibrationError(
                    f"{path} is not a Modelly calibration checkpoint"
                )
            file.readline()  # the Modelly version that wrote it
            calibration = pickle.loads(file.read())  # noqa: S301 - trusted files only
        if not isinstance(calibration, cls):
            raise CalibrationError(f"{path} holds a {type(calibration).__name__}")
        return calibration

    def __getstate__(self) -> dict[str, Any]:
        """Everything but the temporary folder (a resumed run makes its own)."""
        return {**vars(self), "_temporary": None}
