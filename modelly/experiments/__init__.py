"""Experiments and sweeps: a parameter study that runs anywhere and resumes.

``Experiment`` ties a model, a :class:`ScenarioSpace`, a design
(:mod:`~modelly.experiments.designs`), replicates, steps and outputs to a
results store of Parquet files with a DuckDB view. ``run(executor=...)`` runs
it serially, on threads, processes, Dask, Ray, or a SLURM or PBS job array;
the results are the same on all of them. Needs
``pip install "modelly-abm[experiments]"``.
"""

from modelly.experiments import designs
from modelly.experiments.designs import Design
from modelly.experiments.executors import (
    Executor,
    available_executors,
    get_executor,
    register_executor,
)
from modelly.experiments.experiment import (
    Experiment,
    ExperimentError,
    RunReport,
)
from modelly.experiments.space import Choice, Fixed, Range, ScenarioSpace
from modelly.experiments.store import Results, ResultsStore, StoreMismatchError
from modelly.experiments.tasks import RunOutcome, RunTask

__all__ = [
    "Choice",
    "Design",
    "Executor",
    "Experiment",
    "ExperimentError",
    "Fixed",
    "Range",
    "Results",
    "ResultsStore",
    "RunOutcome",
    "RunReport",
    "RunTask",
    "ScenarioSpace",
    "StoreMismatchError",
    "available_executors",
    "designs",
    "get_executor",
    "register_executor",
]
