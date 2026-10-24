"""``Experiment``: a study (space, design, replicates, outputs) that runs anywhere.

Example:
    >>> from modelly.experiments import Experiment, ScenarioSpace, designs
    >>> experiment = Experiment(
    ...     model=Epidemic,
    ...     space=ScenarioSpace(beta=(0.05, 0.5), gamma=(0.05, 0.3), vaccination=[0.0, 0.2]),
    ...     design=designs.latin_hypercube(200),
    ...     replicates=20,
    ...     steps=365,
    ...     outputs=["infected", "recovered"],
    ...     store="runs/epidemic",
    ...     seed=7,
    ... )  # doctest: +SKIP
    >>> experiment.run(executor="processes", max_parallel=8)  # doctest: +SKIP
    >>> experiment.results().query("SELECT beta, max(infected) FROM runs GROUP BY beta")  # doctest: +SKIP

Every (design point, replicate) gets the SeedSequence child
``SeedSequence(seed, spawn_key=(point, replicate))``: its numbers depend on
nothing else, so the results are the same on every executor, in any order,
and a rerun skips the runs whose seed is already in the store.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tqdm.auto import tqdm

from modelly.experiments.designs import Design, FullFactorial
from modelly.experiments.executors import Executor, get_executor
from modelly.experiments.space import ScenarioSpace
from modelly.experiments.store import RESERVED, Results, ResultsStore
from modelly.experiments.tasks import FAILED, RunOutcome, RunTask, reference, resolve
from modelly.scenarios import Scenario

DEFAULT_STEPS = 100
DEFAULT_STORE = "experiment-results"
DEFAULT_EXECUTOR = "processes"
# The design's own stream: a spawn key no (point, replicate) pair can take.
DESIGN_STREAM = (np.iinfo(np.uint32).max,)
ON_ERROR = ("record", "skip", "raise")
Progress = Callable[[int, int, RunOutcome], None]


class ExperimentError(RuntimeError):
    """A run failed and the experiment was asked to stop (``on_error="raise"``)."""

    def __init__(self, outcome: RunOutcome) -> None:
        """Keep the failed run's outcome; its traceback is the message."""
        super().__init__(
            f"run {outcome.run_id} (seed {outcome.seed}) failed:\n{outcome.error}"
        )
        self.outcome = outcome


@dataclass
class RunReport:
    """What one ``Experiment.run`` did: runs skipped, finished and failed."""

    total: int
    skipped: int
    done: int = 0
    failed: list[RunOutcome] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Whether no run failed."""
        return not self.failed

    def add(self, outcome: RunOutcome) -> None:
        """Count one outcome."""
        if outcome.status == FAILED:
            self.failed.append(outcome)
        else:
            self.done += 1


def scenario_class(model: type) -> type[Scenario] | None:
    """The Scenario subclass ``model``'s ``scenario`` argument defaults to, if any."""
    parameter = inspect.signature(model).parameters.get("scenario")
    default = None if parameter is None else parameter.default
    if (
        inspect.isclass(default)
        and issubclass(default, Scenario)
        and default is not Scenario
    ):
        return default
    return None


def _outputs(outputs: str | Iterable[str] | Mapping[str, Any]) -> dict[str, str]:
    """Outputs as ``{name: attribute path or module:function}``."""
    if isinstance(outputs, str):
        outputs = [outputs]
    if not isinstance(outputs, Mapping):
        outputs = {name: name for name in outputs}
    named = {
        name: spec if isinstance(spec, str) else reference(spec)
        for name, spec in outputs.items()
    }
    if not named:
        raise ValueError("an experiment needs at least one output")
    return named


class Experiment:
    """A parameter study: every design point, ``replicates`` times, ``steps`` steps each.

    Args:
        model: the Model class, or ``"package.module:Class"`` / ``"path/model.py:Class"``.
        space: the ScenarioSpace (checked against the model's Scenario class).
        design: which points to run (default: a full factorial).
        replicates: runs per design point, each with its own seed.
        steps: steps per run; a run stops early when ``model.running`` is False.
        outputs: what each step records: attribute or method names, or a mapping
            of column names to attribute names or functions of the model.
        store: the results folder (Parquet files and a DuckDB view).
        seed: the experiment's seed; with it, every run's seed.
        on_error: ``"record"`` a failed run in the store, ``"skip"`` it, or
            ``"raise"`` an ExperimentError (after recording it).
        retries: extra attempts for a failing run before it counts as failed.
    """

    def __init__(
        self,
        model: type | str,
        space: ScenarioSpace,
        design: Design | None = None,
        replicates: int = 1,
        steps: int = DEFAULT_STEPS,
        outputs: str | Iterable[str] | Mapping[str, Any] = (),
        store: str | Path = DEFAULT_STORE,
        seed: int = 0,
        on_error: str = "record",
        retries: int = 0,
    ) -> None:
        """Check the study's definition; nothing runs before ``run``."""
        self.model = model if isinstance(model, str) else reference(model)
        scenario = scenario_class(resolve(self.model))
        self.space = space.typed(scenario) if scenario is not None else space
        self.design = FullFactorial() if design is None else design
        self.replicates, self.steps, self.seed = replicates, steps, seed
        self.outputs = _outputs(outputs)
        self.store = ResultsStore(Path(store).resolve())
        self.on_error, self.retries = on_error, retries
        self._validate()

    def _validate(self) -> None:
        """Reject values that cannot make a valid study."""
        if self.on_error not in ON_ERROR:
            raise ValueError(
                f"on_error must be one of {ON_ERROR}, got {self.on_error!r}"
            )
        if min(self.replicates, self.steps) < 0 or self.replicates == 0:
            raise ValueError("replicates must be at least 1 and steps at least 0")
        if self.seed < 0 or self.retries < 0:
            raise ValueError("seed and retries must be non-negative integers")
        clashes = set(RESERVED) & (set(self.space.names) | set(self.outputs))
        clashes |= set(self.space.names) & set(self.outputs)
        if clashes:
            raise ValueError(f"column names used twice or reserved: {sorted(clashes)}")

    @cached_property
    def points(self) -> list[dict[str, Any]]:
        """The design points, the same for the same seed."""
        stream = np.random.SeedSequence(self.seed, spawn_key=DESIGN_STREAM)
        return self.design.points(self.space, np.random.default_rng(stream))

    def tasks(self) -> list[RunTask]:
        """One task per (design point, replicate), points first."""
        common = {"model": self.model, "entropy": self.seed, "steps": self.steps}
        common |= {"outputs": self.outputs, "store": str(self.store.path)}
        common |= {"retries": self.retries, "record_failures": self.on_error != "skip"}
        return [
            RunTask(params=params, point=point, replicate=replicate, **common)
            for point, params in enumerate(self.points)
            for replicate in range(self.replicates)
        ]

    def pending(self) -> list[RunTask]:
        """The tasks whose seed has no results in the store yet."""
        finished = self.store.finished()
        return [task for task in self.tasks() if task.seed not in finished]

    def fingerprint(self) -> dict[str, Any]:
        """What makes two experiments the same (replicates may grow)."""
        return {
            "model": self.model,
            "points": self.points,
            "steps": self.steps,
            "outputs": self.outputs,
            "seed": self.seed,
            "design": self.design.to_dict(),
        }

    def run(
        self,
        executor: str | Executor = DEFAULT_EXECUTOR,
        max_parallel: int | None = None,
        progress: bool | Progress = False,
        **options: Any,
    ) -> RunReport:
        """Run every pending task on ``executor``; finished runs are skipped.

        ``options`` go to the executor (``partition=``, ``address=``...);
        ``progress=True`` shows a bar, a callable gets ``(done, total, outcome)``.
        """
        runner = get_executor(executor, **options)
        self.store.claim(self.fingerprint())
        todo = self.pending()
        total = len(self.points) * self.replicates
        report = RunReport(total=total, skipped=total - len(todo))
        outcomes = runner.run(todo, max_parallel)
        bar = tqdm(total=len(todo), disable=progress is not True)
        try:
            for count, outcome in enumerate(outcomes, start=1):
                self._handle(report, outcome, count, len(todo), progress)
                bar.update()
        finally:
            bar.close()
            getattr(outcomes, "close", lambda: None)()
        return report

    def _handle(
        self,
        report: RunReport,
        outcome: RunOutcome,
        count: int,
        total: int,
        progress: bool | Progress,
    ) -> None:
        """Count an outcome, report progress, and stop on a failure when asked."""
        report.add(outcome)
        if callable(progress):
            progress(count, total, outcome)
        if outcome.status == FAILED and self.on_error == "raise":
            raise ExperimentError(outcome)

    def results(self) -> Results:
        """The finished runs: ``results().query("SELECT ... FROM runs")``, ``.df()``."""
        return self.store.results()

    def failures(self) -> pd.DataFrame:
        """The recorded failures: run, parameters, attempts and traceback."""
        return self.store.failures()
